#!/usr/bin/env python3
"""Tests for the Human Hands MCP wrapper (jdawgs_mcp/human_hands.py).

Three parts:
  A. Unit tests — validation against the live contract's submission
     schema and the totals math (no network at all).
  B. MCP integration — the real server over stdio, pointed at a LOCAL
     stub of the inbox API (HUMAN_HANDS_BASE_URL). The stub counts POSTs
     so the tests prove previews/dry-runs submit nothing and a real post
     submits exactly once. No live job is ever posted.
  C. Live discovery — one read-only GET against the real
     /api/discovery endpoint through the MCP tool. Read-only; safe.

Exit code 0 = all checks passed.
"""
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from jdawgs_mcp import human_hands as hh  # noqa: E402

passed = []

VALID = {
    "task": "Check the storefront sign is lit",
    "details": "Visit the bakery at opening time, confirm the open sign "
               "is on and the posted hours match the door, then send the "
               "photo proof described.",
    "category": "Verify in person",
    "location": "Springfield, MO",
    "pay_usd": 40,
    "photo_proof_required": "One photo of the storefront showing the lit "
                            "open sign and the hours posted on the door.",
    "agent": {"id": "agent-test-1", "name": "Test Agent",
              "contact": "test@example.com"},
}


def expect_errors(payload, needle, label):
    errs = hh.validate_job(payload)
    assert errs, f"{label}: expected validation errors, got none"
    assert any(needle in e for e in errs), f"{label}: {needle!r} not in {errs}"
    passed.append(f"A validation rejects {label}")


# ---------------------------------------------------------------- Part A
assert hh.validate_job(VALID) == [], hh.validate_job(VALID)
passed.append("A validation accepts the reference valid payload")

obj_loc = dict(VALID, location={"area": "Springfield, MO",
                                "address": "1 Main St"})
assert hh.validate_job(obj_loc) == [], hh.validate_job(obj_loc)
passed.append("A validation accepts the object form of location")

expect_errors(dict(VALID, category="Deliver a package"), "category",
              "a category outside the five contract values")
expect_errors(dict(VALID, agent="agent-test-1"), "agent must be an object",
              "agent given as a plain string")
expect_errors(dict(VALID, photo_proof_required=True),
              "photo_proof_required must be a string",
              "photo_proof_required given as a boolean")
expect_errors(dict(VALID, task="Short"), "task is too short",
              "a task under 10 characters")
expect_errors(dict(VALID, details="Too short."), "details is too short",
              "details under 20 characters")
expect_errors(dict(VALID, pay_usd=0), "pay_usd must be greater than 0",
              "pay_usd of 0")
expect_errors(dict(VALID, pay_usd=True), "pay_usd must be a number",
              "pay_usd given as a boolean")
expect_errors(dict(VALID, pay_usd=10001), "pay_usd must be at most 10000",
              "pay_usd over the 10000 cap")
expect_errors(dict(VALID, surprise_field=1), "unknown field",
              "an unknown field (the API rejects these with a 400)")
expect_errors(dict(VALID, agent={"name": "No way to reach me"}),
              "at least one of id or contact",
              "an agent with neither id nor contact")
expect_errors(dict(VALID, location={"address": "1 Main St"}),
              "location.area is required", "a location object with no area")
expect_errors(dict(VALID, steps=["ok"] * 21), "steps has too many items",
              "more than 20 steps")
expect_errors(dict(VALID, needed_by="2020-01-01T00:00:00Z"),
              "needed_by must be in the future", "a needed_by in the past")
no_agent = {k: v for k, v in VALID.items() if k != "agent"}
expect_errors(no_agent, "missing required field: agent",
              "a missing agent (wrapper requires it for payer follow-up)")

t = hh.compute_totals(40)
assert t["worker_pay_usd"] == 40 and t["platform_fee_usd"] == 6 \
    and t["payer_total_usd"] == 46, t
passed.append("A totals: $40 posted -> worker $40 + fee $6 = payer $46 "
              "(the contract's own example)")
t = hh.compute_totals(33.33)
assert t["platform_fee_usd"] == 5.0 and t["payer_total_usd"] == 38.33, t
passed.append("A totals: $33.33 -> fee $5.00 (half-up), total $38.33")
t = hh.compute_totals(10)
assert t["platform_fee_usd"] == 1.5 and t["payer_total_usd"] == 11.5, t
passed.append("A totals: $10 -> fee $1.50, total $11.50")

prev = hh.preview_job(VALID)
assert prev["valid"] and prev["dry_run"] and prev["submitted"] is False, prev
assert prev["totals"]["payer_total_usd"] == 46, prev
passed.append("A preview_job: valid payload previews with $46 total, "
              "submitted=False")
bad_prev = hh.preview_job(dict(VALID, category="Nope"))
assert bad_prev["valid"] is False and bad_prev["errors"], bad_prev
passed.append("A preview_job: invalid payload returns errors, no totals")

# ---------------------------------------------------------------- Part B
STUB_CONTRACT = {
    "service": "Human Hands for AIs — AI job-posting inbox (LOCAL STUB)",
    "version": "stub-1",
    "categories": hh.CATEGORIES,
    "pay_model": {"worker_percent": 100, "platform_fee_percent": 15,
                  "tips_percent_to_worker": 100,
                  "example": {"pay_usd": 40, "worker_pay_usd": 40,
                              "platform_fee_usd": 6, "payer_total_usd": 46}},
    "endpoints": {"submit_job": {"method": "POST", "path": "/api/jobs"},
                  "discovery": {"method": "GET", "path": "/api/discovery"}},
}


class StubState:
    posts = 0
    jobs = {}


class StubHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # keep test output clean
        pass

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/discovery":
            return self._send(200, STUB_CONTRACT)
        if self.path.startswith("/api/jobs/"):
            if self.headers.get("Authorization") != "Bearer test-feed-token":
                return self._send(401, {"error": "operator only"})
            job = StubState.jobs.get(self.path.rsplit("/", 1)[1])
            if job is None:
                return self._send(404, {"error": "not found"})
            return self._send(200, job)
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/api/jobs":
            return self._send(404, {"error": "not found"})
        body = json.loads(self.rfile.read(
            int(self.headers.get("Content-Length", 0))))
        unknown = sorted(set(body) - hh.JOB_FIELDS)
        if unknown:
            return self._send(400, {"error": "unknown fields",
                                    "fields": unknown})
        StubState.posts += 1
        job = dict(body)
        job["id"] = f"job-stub-{StubState.posts}"
        job["status"] = "pending_review"
        job["totals"] = hh.compute_totals(body["pay_usd"])
        StubState.jobs[job["id"]] = job
        return self._send(201, job)


stub = ThreadingHTTPServer(("127.0.0.1", 0), StubHandler)
threading.Thread(target=stub.serve_forever, daemon=True).start()
STUB_BASE = f"http://127.0.0.1:{stub.server_address[1]}"


class McpClient:
    def __init__(self, extra_env):
        env = dict(os.environ)
        env.pop("HUMAN_HANDS_BASE_URL", None)
        env.pop("HUMAN_HANDS_FEED_TOKEN", None)
        env.update(extra_env)
        self.proc = subprocess.Popen(
            [sys.executable, "server.py"], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, text=True, cwd=HERE, env=env)
        self._id = 0
        init = self.request("initialize", {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "hh-test", "version": "0.1.0"}})
        assert init["serverInfo"]["name"] == "jdawgs-mcp", init
        self.notify("notifications/initialized")

    def request(self, method, params=None):
        self._id += 1
        self.proc.stdin.write(json.dumps(
            {"jsonrpc": "2.0", "id": self._id, "method": method,
             "params": params or {}}) + "\n")
        self.proc.stdin.flush()
        resp = json.loads(self.proc.stdout.readline())
        assert resp.get("id") == self._id, resp
        assert "error" not in resp, resp
        return resp["result"]

    def notify(self, method):
        self.proc.stdin.write(json.dumps(
            {"jsonrpc": "2.0", "method": method}) + "\n")
        self.proc.stdin.flush()

    def call(self, name, args=None):
        res = self.request("tools/call",
                           {"name": name, "arguments": args or {}})
        return res.get("isError", False), json.loads(res["content"][0]["text"])

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=5)


client = McpClient({"HUMAN_HANDS_BASE_URL": STUB_BASE})
names = [t["name"] for t in client.request("tools/list")["tools"]]
for want in ("human_hands_discover", "human_hands_preview_job",
             "human_hands_post_job", "human_hands_job_status"):
    assert want in names, names
passed.append(f"B tools/list: all 4 Human Hands tools present "
              f"({len(names)} tools total)")

err, doc = client.call("human_hands_discover")
assert not err and doc["contract"]["version"] == "stub-1", doc
assert doc["contract"]["categories"] == hh.CATEGORIES, doc
passed.append("B discover: returns the stub contract's real shape "
              "(categories + pay model)")

err, prev = client.call("human_hands_preview_job", VALID)
assert not err and prev["valid"] and prev["totals"]["payer_total_usd"] == 46, prev
assert StubState.posts == 0, StubState.posts
passed.append("B preview via MCP: $46 total and the stub received "
              "ZERO posts (true dry-run)")

err, dry = client.call("human_hands_post_job", dict(VALID, dry_run=True))
assert not err and dry["dry_run"] and dry["submitted"] is False, dry
assert StubState.posts == 0, StubState.posts
passed.append("B post_job dry_run=true: preview returned, stub still "
              "at ZERO posts")

err, out = client.call("human_hands_post_job",
                       dict(VALID, idempotency_key="test-key-1"))
assert not err and out["submitted"] is True, out
assert out["response"]["status"] == "pending_review", out
assert out["response"]["id"] == "job-stub-1", out
assert StubState.posts == 1, StubState.posts
passed.append("B post_job: exactly ONE post reached the stub; response "
              "is 201 pending_review with the job id")

err, st = client.call("human_hands_job_status", {"job_id": "job-stub-1"})
assert err and st.get("operator_only") is True, st
passed.append("B status without a feed token: honest operator-only "
              "error (no invented status)")

err, bad = client.call("human_hands_post_job",
                       dict(VALID, category="Wrong category"))
assert err and "errors" in bad, bad
assert StubState.posts == 1, StubState.posts
passed.append("B post_job with a bad category: rejected locally, "
              "nothing submitted")
client.close()

op = McpClient({"HUMAN_HANDS_BASE_URL": STUB_BASE,
                "HUMAN_HANDS_FEED_TOKEN": "test-feed-token"})
err, st = op.call("human_hands_job_status", {"job_id": "job-stub-1"})
assert not err and st["job"]["status"] == "pending_review", st
assert st["job"]["totals"]["payer_total_usd"] == 46, st
passed.append("B status WITH the operator token: real job returned "
              "(pending_review, $46 totals)")
op.close()
stub.shutdown()

# ---------------------------------------------------------------- Part C
live = McpClient({})
err, doc = live.call("human_hands_discover")
assert not err, doc
contract = doc["contract"]
assert contract["categories"] == hh.CATEGORIES, contract["categories"]
ex = contract["pay_model"]["example"]
assert ex["pay_usd"] == 40 and ex["payer_total_usd"] == 46, ex
assert contract["endpoints"]["submit_job"]["path"] == "/api/jobs", contract
passed.append("C live discovery: real contract fetched read-only — "
              "categories match the wrapper, $40 -> $46 example confirmed, "
              "POST /api/jobs present")
live.close()

print("ALL HUMAN HANDS CHECKS PASSED")
for line in passed:
    print("  ✓", line)
