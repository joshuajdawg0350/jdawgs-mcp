#!/usr/bin/env python3
"""Human Hands for AIs — live hiring wrapper for the J-Dawgs MCP server.

Wraps the Human Hands AI job-posting inbox API:

  GET  {base}/api/discovery   public contract document (no auth)
  POST {base}/api/jobs        submit one job (no auth; moderated queue —
                              every job starts as pending_review)
  GET  {base}/api/jobs/{id}   OPERATOR ONLY (Authorization: Bearer
                              <FEED_TOKEN>) — there is no public status
                              endpoint for posters, and this module never
                              pretends otherwise.

Dry-run / preview is CLIENT-SIDE by design: the live API rejects unknown
fields, and its published contract has no dry-run flag, so a preview is a
full local validation of the payload against the contract's submission
schema plus a locally computed totals split (worker pay, 15% payer fee,
payer total). A preview NEVER touches the network.

Configuration (environment):
  HUMAN_HANDS_BASE_URL    override the inbox base URL (used by tests to
                          point at a local stub; default is the live inbox)
  HUMAN_HANDS_FEED_TOKEN  operator feed token; only needed by the
                          job-status tool, which is operator-only.

Dependencies: Python 3.9+ standard library only — same rule as server.py.
"""
import json
import math
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

DEFAULT_BASE_URL = "https://human-hands-ai-inbox-joshuajdawg0350-1282.vercel.app"
WRAPPER_VERSION = "0.2.0"

# The five posting categories, exactly as published by GET /api/discovery.
CATEGORIES = [
    "Verify in person",
    "Pick up & deliver",
    "Property check",
    "In-person visit",
    "Install & assembly",
]

FEE_PERCENT = 15
MAX_BODY_CHARS = 32768

# Fields the live contract accepts in a POST /api/jobs body. Anything else
# is rejected by the server with a 400, so the wrapper rejects it locally.
JOB_FIELDS = {
    "task", "details", "category", "location", "pay_usd",
    "photo_proof_required", "estimated_time", "distance", "steps",
    "needed_by", "agent", "idempotency_key",
}
REQUIRED_FIELDS = ["task", "details", "category", "location", "pay_usd",
                   "photo_proof_required"]
# The MCP post tool additionally requires `agent`: the inbox accepts a
# submission without it, but then the operator cannot follow up with the
# payer about payment, so the wrapper treats it as required.
TOOL_REQUIRED_FIELDS = REQUIRED_FIELDS + ["agent"]
AGENT_FIELDS = {"id", "name", "contact"}
LOCATION_FIELDS = {"area", "address"}


def base_url():
    return os.environ.get("HUMAN_HANDS_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def feed_token():
    return os.environ.get("HUMAN_HANDS_FEED_TOKEN", "").strip()


# ---------------------------------------------------------------------------
# Money
# ---------------------------------------------------------------------------

def _money(d):
    """Decimal -> int when whole, else float (matches the contract's
    example style: $40 -> fee 6, total 46)."""
    if d == d.to_integral_value():
        return int(d)
    return float(d)


def compute_totals(pay_usd):
    """Worker pay / payer fee / payer total for a posted price.

    The worker keeps 100% of the posted price; the payer pays the posted
    price plus a 15% fee; tips (100% to the worker) are handled at payment
    time, not at posting, so they never appear here.
    """
    pay = Decimal(str(pay_usd)).quantize(Decimal("0.01"),
                                          rounding=ROUND_HALF_UP)
    fee = (pay * Decimal(FEE_PERCENT) / Decimal(100)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {
        "pay_usd": _money(pay),
        "worker_pay_usd": _money(pay),
        "platform_fee_percent": FEE_PERCENT,
        "platform_fee_usd": _money(fee),
        "payer_total_usd": _money(pay + fee),
        "tips": "100% to the worker, handled at payment time (not in totals)",
    }


# ---------------------------------------------------------------------------
# Validation — mirrors the submission_schema published by GET /api/discovery
# ---------------------------------------------------------------------------

def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _check_str(errors, field, value, min_len, max_len):
    if not isinstance(value, str):
        errors.append(f"{field} must be a string, got {type(value).__name__}")
        return
    if len(value) < min_len:
        errors.append(f"{field} is too short ({len(value)} chars; "
                      f"minimum {min_len})")
    if len(value) > max_len:
        errors.append(f"{field} is too long ({len(value)} chars; "
                      f"maximum {max_len})")


def validate_job(payload):
    """Return a list of contract violations (empty list = valid)."""
    errors = []
    if not isinstance(payload, dict):
        return ["job payload must be a JSON object"]

    unknown = sorted(set(payload) - JOB_FIELDS)
    if unknown:
        errors.append("unknown field(s) the API rejects: "
                      + ", ".join(unknown))

    for field in TOOL_REQUIRED_FIELDS:
        if field not in payload or payload[field] is None:
            errors.append(f"missing required field: {field}")

    if "task" in payload and payload["task"] is not None:
        _check_str(errors, "task", payload["task"], 10, 200)
    if "details" in payload and payload["details"] is not None:
        _check_str(errors, "details", payload["details"], 20, 2000)

    if "category" in payload and payload["category"] is not None:
        if payload["category"] not in CATEGORIES:
            errors.append("category must be exactly one of: "
                          + "; ".join(CATEGORIES))

    if "location" in payload and payload["location"] is not None:
        loc = payload["location"]
        if isinstance(loc, str):
            _check_str(errors, "location", loc, 3, 200)
        elif isinstance(loc, dict):
            extra = sorted(set(loc) - LOCATION_FIELDS)
            if extra:
                errors.append("location has unknown field(s): "
                              + ", ".join(extra))
            if "area" not in loc:
                errors.append("location.area is required")
            else:
                _check_str(errors, "location.area", loc["area"], 3, 200)
            if "address" in loc:
                _check_str(errors, "location.address", loc["address"], 0, 300)
        else:
            errors.append("location must be a string (area) or an object "
                          "{ area, address? }")

    if "pay_usd" in payload and payload["pay_usd"] is not None:
        pay = payload["pay_usd"]
        if not _is_number(pay):
            errors.append("pay_usd must be a number (USD)")
        elif not math.isfinite(pay):
            errors.append("pay_usd must be a finite number")
        elif pay <= 0:
            errors.append("pay_usd must be greater than 0")
        elif pay > 10000:
            errors.append("pay_usd must be at most 10000")

    if ("photo_proof_required" in payload
            and payload["photo_proof_required"] is not None):
        _check_str(errors, "photo_proof_required",
                   payload["photo_proof_required"], 10, 500)

    if "estimated_time" in payload and payload["estimated_time"] is not None:
        _check_str(errors, "estimated_time", payload["estimated_time"], 0, 100)
    if "distance" in payload and payload["distance"] is not None:
        _check_str(errors, "distance", payload["distance"], 0, 100)

    if "steps" in payload and payload["steps"] is not None:
        steps = payload["steps"]
        if not isinstance(steps, list):
            errors.append("steps must be an array of strings")
        else:
            if len(steps) > 20:
                errors.append("steps has too many items (maximum 20)")
            for i, step in enumerate(steps):
                _check_str(errors, f"steps[{i}]", step, 1, 300)

    if "needed_by" in payload and payload["needed_by"] is not None:
        nb = payload["needed_by"]
        if not isinstance(nb, str):
            errors.append("needed_by must be an ISO 8601 date-time string")
        else:
            try:
                dt = datetime.fromisoformat(nb.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt <= datetime.now(timezone.utc):
                    errors.append("needed_by must be in the future")
            except ValueError:
                errors.append("needed_by is not a valid ISO 8601 date-time")

    if "agent" in payload and payload["agent"] is not None:
        agent = payload["agent"]
        if not isinstance(agent, dict):
            errors.append("agent must be an object { id, name, contact } — "
                          "a plain string is rejected by the API contract")
        else:
            extra = sorted(set(agent) - AGENT_FIELDS)
            if extra:
                errors.append("agent has unknown field(s): "
                              + ", ".join(extra))
            if "id" in agent:
                _check_str(errors, "agent.id", agent["id"], 3, 100)
            if "name" in agent:
                _check_str(errors, "agent.name", agent["name"], 1, 100)
            if "contact" in agent:
                _check_str(errors, "agent.contact", agent["contact"], 1, 300)
            if not (agent.get("id") or agent.get("contact")):
                errors.append("agent needs at least one of id or contact so "
                              "the operator can follow up on payment")

    if ("idempotency_key" in payload
            and payload["idempotency_key"] is not None):
        _check_str(errors, "idempotency_key", payload["idempotency_key"],
                   1, 128)

    if not errors:
        body_len = len(json.dumps(payload))
        if body_len > MAX_BODY_CHARS:
            errors.append(f"serialized job body is {body_len} characters; "
                          f"the API accepts at most {MAX_BODY_CHARS}")
    return errors


def preview_job(payload):
    """Client-side dry-run: validate + compute totals. NO network call,
    NOTHING is submitted. Clearly labeled as a local preview."""
    errors = validate_job(payload)
    if errors:
        return {
            "dry_run": True,
            "submitted": False,
            "valid": False,
            "errors": errors,
            "note": "LOCAL PREVIEW ONLY — nothing was submitted to Human "
                    "Hands. Fix the errors and preview again, or post for "
                    "real with human_hands_post_job.",
        }
    return {
        "dry_run": True,
        "submitted": False,
        "valid": True,
        "payload": payload,
        "totals": compute_totals(payload["pay_usd"]),
        "would_submit_to": f"POST {base_url()}/api/jobs",
        "note": "LOCAL PREVIEW ONLY — nothing was submitted to Human "
                "Hands. The API has no dry-run flag (unknown fields are "
                "rejected), so this preview is computed by the wrapper. "
                "A real post starts as pending_review in the moderated "
                "queue; the server recomputes the totals itself.",
    }


# ---------------------------------------------------------------------------
# HTTP (stdlib urllib only)
# ---------------------------------------------------------------------------

class HandsNetworkError(Exception):
    pass


def _request(method, path, body=None, extra_headers=None):
    url = base_url() + path
    headers = {"Accept": "application/json",
               "User-Agent": f"jdawgs-mcp/{WRAPPER_VERSION} "
                             "(Human Hands wrapper)"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, data=data, headers=headers,
                                 method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(raw)
        except ValueError:
            parsed = {"raw": raw[:500]}
        return exc.code, parsed
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise HandsNetworkError(f"{method} {url} failed: {exc}")


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def tool_discover():
    """GET /api/discovery — the live, public Human Hands contract."""
    try:
        status, doc = _request("GET", "/api/discovery")
    except HandsNetworkError as exc:
        return {"error": str(exc),
                "note": "Could not reach the live discovery endpoint. The "
                        "bundled human_hands_info tool carries a dated, "
                        "offline summary of the service."}
    if status != 200:
        return {"error": f"discovery endpoint returned HTTP {status}",
                "response": doc}
    return {
        "source": f"GET {base_url()}/api/discovery",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "contract": doc,
    }


def tool_post_job(args):
    """Validate locally, then POST /api/jobs — unless dry_run is set, in
    which case this is exactly human_hands_preview_job and nothing is
    submitted."""
    args = dict(args or {})
    dry_run = bool(args.pop("dry_run", False))
    payload = {k: v for k, v in args.items() if v is not None}
    if dry_run:
        return preview_job(payload)

    errors = validate_job(payload)
    if errors:
        return {"error": "job failed local contract validation; "
                         "nothing was submitted",
                "errors": errors}

    idem = payload.pop("idempotency_key", None)
    headers = {}
    if idem:
        headers["X-Idempotency-Key"] = str(idem)
    try:
        status, doc = _request("POST", "/api/jobs", body=payload,
                               extra_headers=headers)
    except HandsNetworkError as exc:
        return {"error": str(exc), "submitted": False}
    if status == 201:
        return {
            "submitted": True,
            "http_status": 201,
            "totals_preview": compute_totals(payload["pay_usd"]),
            "note": "Accepted into the moderated queue. Every job starts "
                    "as pending_review; nothing reaches workers until the "
                    "operator reviews it.",
            "response": doc,
        }
    return {"error": f"the inbox returned HTTP {status}; "
                     "the job was not accepted",
            "submitted": False, "response": doc}


def tool_job_status(args):
    """GET /api/jobs/{id} — OPERATOR ONLY per the published contract.

    There is no public status endpoint for posters: the discovery document
    lists the job feed and single-job reads as operator-only (Bearer
    FEED_TOKEN). Without that token this tool says so plainly instead of
    inventing a status."""
    job_id = str((args or {}).get("job_id", "")).strip()
    if not job_id:
        return {"error": "job_id is required"}
    token = feed_token()
    if not token:
        return {
            "error": "job status is operator-only",
            "operator_only": True,
            "detail": "The Human Hands discovery contract lists GET "
                      "/api/jobs/{id} as operator-only (Authorization: "
                      "Bearer <FEED_TOKEN>); posters cannot poll status "
                      "publicly. A submitted job starts as pending_review, "
                      "and the operator follows up through the agent "
                      "contact given at posting. Set HUMAN_HANDS_FEED_TOKEN "
                      "in the server environment to use this tool as the "
                      "operator.",
        }
    try:
        status, doc = _request(
            "GET", f"/api/jobs/{job_id}",
            extra_headers={"Authorization": f"Bearer {token}"})
    except HandsNetworkError as exc:
        return {"error": str(exc)}
    if status == 200:
        return {"job_id": job_id, "job": doc}
    return {"error": f"status lookup returned HTTP {status}",
            "job_id": job_id, "response": doc}


# ---------------------------------------------------------------------------
# MCP tool definitions (merged into server.py's TOOLS list)
# ---------------------------------------------------------------------------

_JOB_PROPERTIES = {
    "task": {"type": "string", "minLength": 10, "maxLength": 200,
             "description": "What needs doing, in one line."},
    "details": {"type": "string", "minLength": 20, "maxLength": 2000,
                "description": "Full task description, including any steps."},
    "category": {"type": "string", "enum": CATEGORIES,
                 "description": "Exactly one of the five posting categories."},
    "location": {"description": "Where the job is: a string (area) or an "
                                "object { area, address? }."},
    "pay_usd": {"type": "number", "exclusiveMinimum": 0, "maximum": 10000,
                "description": "Flat worker pay in USD. The worker keeps "
                               "100% of it; the payer total adds a 15% fee."},
    "photo_proof_required": {"type": "string", "minLength": 10,
                             "maxLength": 500,
                             "description": "A short description of exactly "
                                            "what photo proof the worker "
                                            "must send back (a string, "
                                            "never true/false)."},
    "agent": {"type": "object",
              "description": "Who is posting, so the operator can follow "
                             "up on payment: { id?, name?, contact? } with "
                             "at least one of id or contact. Never send "
                             "secrets or credentials here.",
              "properties": {
                  "id": {"type": "string"},
                  "name": {"type": "string"},
                  "contact": {"type": "string"}}},
    "estimated_time": {"type": "string",
                       "description": "Optional, e.g. 'about 30 minutes'."},
    "distance": {"type": "string",
                 "description": "Optional poster hint, e.g. 'within "
                                "Springfield'."},
    "steps": {"type": "array", "maxItems": 20,
              "items": {"type": "string"},
              "description": "Optional step list."},
    "needed_by": {"type": "string",
                  "description": "Optional ISO 8601 deadline, in the future."},
    "idempotency_key": {"type": "string",
                        "description": "Optional. Resubmitting the same "
                                       "key for the same agent returns the "
                                       "original job instead of a duplicate."},
}
_JOB_REQUIRED = ["task", "details", "category", "location", "pay_usd",
                 "photo_proof_required", "agent"]

TOOLS = [
    {
        "name": "human_hands_discover",
        "description": "Fetch the LIVE Human Hands for AIs discovery "
                       "contract (GET /api/discovery): endpoints, the five "
                       "posting categories, the submission schema, and the "
                       "pay model (worker keeps 100% of the posted price, "
                       "payer adds a 15% fee, tips 100% to the worker).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "human_hands_preview_job",
        "description": "DRY-RUN a Human Hands job post without submitting "
                       "anything: the payload is validated locally against "
                       "the live contract's submission schema and the "
                       "totals are computed (worker pay, 15% payer fee, "
                       "payer total). The API has no dry-run flag, so this "
                       "preview is entirely client-side and is labeled as "
                       "such.",
        "inputSchema": {"type": "object", "properties": _JOB_PROPERTIES,
                        "required": _JOB_REQUIRED},
    },
    {
        "name": "human_hands_post_job",
        "description": "Post a real job to Human Hands for AIs (POST "
                       "/api/jobs). The payload is validated locally "
                       "first. The job enters a moderated queue as "
                       "pending_review — nothing reaches workers until the "
                       "operator approves it. Set dry_run=true to validate "
                       "and preview totals WITHOUT submitting (identical "
                       "to human_hands_preview_job).",
        "inputSchema": {"type": "object",
                        "properties": dict(
                            _JOB_PROPERTIES,
                            dry_run={"type": "boolean",
                                     "description": "If true, validate "
                                                    "and preview only; "
                                                    "nothing is submitted."}),
                        "required": _JOB_REQUIRED},
    },
    {
        "name": "human_hands_job_status",
        "description": "Look up one job by id (GET /api/jobs/{id}). "
                       "OPERATOR ONLY: the published contract restricts "
                       "job reads to the operator's feed token — there is "
                       "no public status endpoint for posters. Without "
                       "HUMAN_HANDS_FEED_TOKEN in the server environment "
                       "this tool reports that plainly instead of guessing "
                       "a status.",
        "inputSchema": {"type": "object",
                        "properties": {
                            "job_id": {"type": "string",
                                       "description": "The job id returned "
                                                      "when the job was "
                                                      "posted."}},
                        "required": ["job_id"]},
    },
]

TOOL_NAMES = {t["name"] for t in TOOLS}


def call_tool(name, args):
    if name == "human_hands_discover":
        return tool_discover()
    if name == "human_hands_preview_job":
        payload = {k: v for k, v in (args or {}).items() if v is not None}
        return preview_job(payload)
    if name == "human_hands_post_job":
        return tool_post_job(args)
    if name == "human_hands_job_status":
        return tool_job_status(args)
    return {"error": f"Unknown tool {name!r}"}
