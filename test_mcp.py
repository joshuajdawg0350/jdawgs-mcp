#!/usr/bin/env python3
"""Scripted MCP client test for the J-Dawgs MCP server.

Spawns server.py over stdio, performs the MCP handshake, lists tools,
runs real tool calls and a resource read, and asserts on the results.
Exit code 0 = all checks passed.
"""
import json
import subprocess
import sys

proc = subprocess.Popen(
    [sys.executable, "server.py"],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
    cwd="/home/hatch/workspace/mcp/jdawgs-mcp",
)

_id = 0


def send(msg):
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()


def request(method, params=None):
    global _id
    _id += 1
    send({"jsonrpc": "2.0", "id": _id, "method": method, "params": params or {}})
    line = proc.stdout.readline()
    assert line, f"no response to {method}"
    resp = json.loads(line)
    assert resp.get("id") == _id, f"id mismatch on {method}: {resp}"
    assert "error" not in resp, f"{method} returned error: {resp['error']}"
    return resp["result"]


def notify(method):
    send({"jsonrpc": "2.0", "method": method})


passed = []

# 1. Handshake
init = request("initialize", {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {"name": "jdawgs-test-client", "version": "0.1.0"},
})
assert init["serverInfo"]["name"] == "jdawgs-mcp", init
passed.append(f"initialize ok — server {init['serverInfo']['name']} "
              f"v{init['serverInfo']['version']}, protocol {init['protocolVersion']}")
notify("notifications/initialized")

# 2. Ping
request("ping")
passed.append("ping ok")

# 3. Tools list
tools = request("tools/list")["tools"]
names = [t["name"] for t in tools]
expected = {"store_info", "search_tools", "list_tools", "get_tool",
            "find_tool_for_problem", "get_bundles", "human_hands_info"}
assert expected <= set(names), names
passed.append(f"tools/list ok — {len(tools)} tools: {', '.join(names)}")


def call(name, args=None):
    res = request("tools/call", {"name": name, "arguments": args or {}})
    assert not res.get("isError"), f"{name} errored: {res}"
    return json.loads(res["content"][0]["text"])


# 4. store_info (expectations read from the snapshot itself — it grows daily)
import os
snap = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "jdawgs_mcp", "catalog.json")))
info = call("store_info")
assert info["tools_listed"] == len(snap["tools"]), info
assert info["priced_tools"] == sum(1 for t in snap["tools"] if t["price_usd"] > 0), info
passed.append(f"store_info ok — {info['tools_listed']} listed, "
              f"{info['priced_tools']} priced, combined ${info['priced_tools_combined_value_usd']}")

# 5. Catalog search
res = call("search_tools", {"query": "jwt"})
assert res["matches"] >= 1 and any("JWT" in t["name"] for t in res["tools"]), res
jwt = [t for t in res["tools"] if "JWT" in t["name"]][0]
passed.append(f"search_tools('jwt') ok — {res['matches']} match(es); top: "
              f"{jwt['name']} ${jwt['price_usd']} {jwt['url'][:60]}…")

# 6. get_tool with a card payment URL
tool = call("get_tool", {"name": "J-Dawgs Claim Checker"})
assert tool["card_payment_url"] and tool["card_payment_url"].startswith(
    "https://buy.stripe.com/"), tool
passed.append(f"get_tool ok — Claim Checker ${tool['price_usd']}, "
              f"card URL {tool['card_payment_url']}")

# 7. Problem finder
res = call("find_tool_for_problem",
           {"problem": "an email claims to be from a bank and I need to know if it is real"})
assert res["matches"], res
passed.append(f"find_tool_for_problem ok — matched: {res['matches'][0]['tool']}")

# 8. Bundles
b = call("get_bundles")
assert b["bundles"]["unlimited_pass"]["price_usd"] == 99.99, b["bundles"]
assert b["bundles"]["everything_stack"]["price_usd"] == 19.99, b["bundles"]
passed.append("get_bundles ok — Unlimited Pass $99.99, Everything Stack $19.99, "
              f"{len(b['stacks'])} themed stacks")

# 9. Human Hands
hh = call("human_hands_info")
assert any("storm" in c for c in hh["categories"]), hh["categories"]
assert hh["how_to_post_a_job"]["endpoint"].startswith("POST https://"), hh
passed.append(f"human_hands_info ok — {len(hh['categories'])} categories incl. "
              "storm-damage property checks; POST endpoint present")

# 10. Resource read
resources = request("resources/list")["resources"]
assert len(resources) == 3, resources
read = request("resources/read", {"uri": "jdawgs://catalog"})
cat = json.loads(read["contents"][0]["text"])
assert len(cat["tools"]) == len(snap["tools"]), len(cat["tools"])
passed.append(f"resources ok — jdawgs://catalog returns all {len(cat['tools'])} tools")

proc.stdin.close()
proc.wait(timeout=5)

print("ALL CHECKS PASSED")
for line in passed:
    print("  ✓", line)
