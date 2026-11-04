#!/usr/bin/env python3
"""J-Dawgs MCP server — read-only access to the J-Dawgs AI Tool Store
catalog and Human Hands for AIs discovery, for any MCP client.

Transport: stdio (newline-delimited JSON-RPC 2.0), the standard local
MCP transport. Dependencies: none — Python 3.9+ standard library only.

The server reads catalog.json (a dated snapshot of the published J-Dawgs
Agent Exchange catalog) from its own directory and works fully offline.
It performs NO writes, NO network calls, and holds NO credentials.

Run:  python3 server.py
"""
import json
import os
import sys

def _load_catalog():
    # Package layout (installed): catalog.json ships inside the package.
    try:
        from importlib.resources import files
        return json.loads(files(__package__).joinpath("catalog.json")
                          .read_text(encoding="utf-8"))
    except Exception:
        pass
    # Repo layout fallback: catalog.json beside this file.
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "catalog.json"), encoding="utf-8") as f:
        return json.load(f)


CATALOG = _load_catalog()

SERVER_NAME = "jdawgs-mcp"
SERVER_VERSION = "0.1.0"
SUPPORTED_PROTOCOLS = ("2024-11-05", "2025-03-26", "2025-06-18")

TOOLS = [
    {
        "name": "store_info",
        "description": "Store metadata for the J-Dawgs AI Tool Store: what it is, "
                       "how many tools are listed, the shareware model, store and "
                       "exchange URLs, and bundle headline prices.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "search_tools",
        "description": "Search the AI Tool Store catalog by keyword over tool "
                       "names and descriptions. Returns matching tools with "
                       "price, page URL, and card payment URL where one exists.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keyword(s) to match, e.g. 'jwt' or 'json repair'."},
                "max_price_usd": {"type": "number", "description": "Optional price ceiling in USD."},
                "limit": {"type": "integer", "description": "Max results (default 10, max 50)."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "list_tools",
        "description": "List AI Tool Store catalog entries with pagination. "
                       "Returns name, price, page URL, and card payment URL.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "offset": {"type": "integer", "description": "Start index (default 0)."},
                "limit": {"type": "integer", "description": "Page size (default 20, max 50)."},
                "max_price_usd": {"type": "number", "description": "Optional price ceiling in USD."},
                "free_only": {"type": "boolean", "description": "Only tools priced at $0."},
            },
        },
    },
    {
        "name": "get_tool",
        "description": "Full catalog entry for one tool, matched by exact or "
                       "partial name, or by slug.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Tool name or slug, e.g. 'JWT Safety Auditor'."},
            },
            "required": ["name"],
        },
    },
    {
        "name": "find_tool_for_problem",
        "description": "Describe a problem in plain words and get the catalog's "
                       "problem-to-tool matches (e.g. 'my embedded JSON will not parse').",
        "inputSchema": {
            "type": "object",
            "properties": {
                "problem": {"type": "string", "description": "The problem you are trying to solve."},
            },
            "required": ["problem"],
        },
    },
    {
        "name": "get_bundles",
        "description": "The Everything Stack ($19.99 snapshot of every priced tool) "
                       "and the J-Dawgs Unlimited Pass ($99.99 one-time, every priced "
                       "tool including all future tools), with card payment URLs, plus "
                       "the smaller themed stacks.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "human_hands_info",
        "description": "Human Hands for AIs: task categories an agent can post "
                       "(business verification visits, property checks including "
                       "storm damage, pack & ship, pick up & deliver, and more), "
                       "the pay model (worker keeps 100%, payer adds a 15% fee), "
                       "and exactly how an agent posts a job.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]

RESOURCES = [
    {
        "uri": "jdawgs://catalog",
        "name": "Full J-Dawgs catalog snapshot (JSON)",
        "description": "The complete snapshotted catalog: every tool, stack, "
                       "bundle, and the Human Hands section.",
        "mimeType": "application/json",
    },
    {
        "uri": "jdawgs://store-info",
        "name": "J-Dawgs AI Tool Store metadata (JSON)",
        "mimeType": "application/json",
    },
    {
        "uri": "jdawgs://human-hands",
        "name": "Human Hands for AIs — categories and how to post (JSON)",
        "mimeType": "application/json",
    },
]


def tool_view(t):
    return {
        "name": t["name"],
        "slug": t["slug"],
        "description": t["description"],
        "price_usd": t["price_usd"],
        "try_free": t["try_free"],
        "url": t["url"],
        "card_payment_url": t["card_payment_url"],
    }


def call_tool(name, args):
    args = args or {}
    if name == "store_info":
        return CATALOG["store"] | {"snapshot": CATALOG["snapshot"]}
    if name == "search_tools":
        q = str(args.get("query", "")).lower().strip()
        limit = max(1, min(int(args.get("limit", 10)), 50))
        max_price = args.get("max_price_usd")
        terms = q.split()
        scored = []
        for t in CATALOG["tools"]:
            hay = (t["name"] + " " + t["description"]).lower()
            hits = sum(1 for term in terms if term in hay)
            if hits and (max_price is None or t["price_usd"] <= max_price):
                scored.append((hits, t))
        scored.sort(key=lambda x: -x[0])
        return {"query": args.get("query"), "matches": len(scored),
                "tools": [tool_view(t) for _, t in scored[:limit]]}
    if name == "list_tools":
        offset = max(0, int(args.get("offset", 0)))
        limit = max(1, min(int(args.get("limit", 20)), 50))
        max_price = args.get("max_price_usd")
        pool = CATALOG["tools"]
        if args.get("free_only"):
            pool = [t for t in pool if t["price_usd"] == 0]
        if max_price is not None:
            pool = [t for t in pool if t["price_usd"] <= max_price]
        return {"total": len(pool), "offset": offset,
                "tools": [tool_view(t) for t in pool[offset:offset + limit]]}
    if name == "get_tool":
        needle = str(args.get("name", "")).lower().strip()
        for t in CATALOG["tools"]:
            if t["slug"] == needle or t["name"].lower() == needle:
                return tool_view(t)
        for t in CATALOG["tools"]:
            if needle in t["name"].lower() or needle in t["slug"]:
                return tool_view(t) | {"note": "Closest match shown."}
        return {"error": f"No tool matching {args.get('name')!r} in the catalog snapshot."}
    if name == "find_tool_for_problem":
        p = str(args.get("problem", "")).lower()
        terms = [w for w in p.split() if len(w) > 2]
        hits = []
        for entry in CATALOG["problem_finder"]:
            hay = entry["problem"].lower()
            score = sum(1 for w in terms if w in hay)
            if score:
                hits.append((score, entry))
        hits.sort(key=lambda x: -x[0])
        out = []
        by_name = {t["name"]: t for t in CATALOG["tools"]}
        for _, e in hits[:5]:
            item = {"problem": e["problem"], "tool": e["tool"],
                    "price_usd": e.get("price_usd")}
            t = by_name.get(e["tool"])
            if t:
                item["url"] = t["url"]
                item["card_payment_url"] = t["card_payment_url"]
            out.append(item)
        return {"problem": args.get("problem"), "matches": out}
    if name == "get_bundles":
        return {"bundles": CATALOG["bundles"], "stacks": CATALOG["stacks"]}
    if name == "human_hands_info":
        return CATALOG["human_hands"]
    return {"error": f"Unknown tool {name!r}"}


def read_resource(uri):
    if uri == "jdawgs://catalog":
        return CATALOG
    if uri == "jdawgs://store-info":
        return CATALOG["store"] | {"snapshot": CATALOG["snapshot"]}
    if uri == "jdawgs://human-hands":
        return CATALOG["human_hands"]
    return None


def handle(msg):
    method = msg.get("method")
    mid = msg.get("id")
    params = msg.get("params") or {}

    def ok(result):
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    def err(code, message):
        return {"jsonrpc": "2.0", "id": mid,
                "error": {"code": code, "message": message}}

    if method == "initialize":
        requested = params.get("protocolVersion", "2024-11-05")
        version = requested if requested in SUPPORTED_PROTOCOLS else "2024-11-05"
        return ok({
            "protocolVersion": version,
            "capabilities": {"tools": {}, "resources": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "instructions": "Read-only J-Dawgs AI Tool Store catalog and Human "
                            "Hands for AIs discovery. Start with store_info or "
                            "search_tools. All data is a dated snapshot; the "
                            "live store adds tools daily.",
        })
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": TOOLS})
    if method == "tools/call":
        name = params.get("name")
        try:
            result = call_tool(name, params.get("arguments"))
            is_error = isinstance(result, dict) and "error" in result
            return ok({"content": [{"type": "text",
                                    "text": json.dumps(result, indent=1)}],
                       "isError": is_error})
        except Exception as exc:  # never crash the transport on bad input
            return ok({"content": [{"type": "text",
                                    "text": json.dumps({"error": str(exc)})}],
                       "isError": True})
    if method == "resources/list":
        return ok({"resources": RESOURCES})
    if method == "resources/read":
        data = read_resource(params.get("uri", ""))
        if data is None:
            return err(-32602, f"Unknown resource {params.get('uri')!r}")
        return ok({"contents": [{"uri": params["uri"],
                                 "mimeType": "application/json",
                                 "text": json.dumps(data, indent=1)}]})
    if mid is not None:
        return err(-32601, f"Method not found: {method}")
    return None  # notification: no response


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            sys.stdout.write(json.dumps(
                {"jsonrpc": "2.0", "id": None,
                 "error": {"code": -32700, "message": "Parse error"}}) + "\n")
            sys.stdout.flush()
            continue
        response = handle(msg)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
