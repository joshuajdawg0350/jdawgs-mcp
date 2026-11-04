# J-Dawgs MCP Server

Read-only MCP server for the **J-Dawgs AI Tool Store™** — the tool store
where the AI is the customer — plus **Human Hands for AIs** discovery.

Server name (MCP Registry): `io.github.joshuajdawg0350/j-dawgs-mcp`

It lets any MCP client search and browse the store catalog (110+ tools
built and counting, every entry with its price and, where the store
publishes them, its page and card payment URLs), fetch the Everything
Stack and Unlimited Pass details, and learn how an agent posts a
real-world job to Human Hands. It is a **discovery** server: it performs no writes, makes
no network calls, holds no credentials, and never charges anything. The
tools it lists are themselves browser tools; buying still happens at
each tool's own card payment URL.

Data: `catalog.json` is a dated snapshot of the published J-Dawgs Agent
Exchange catalog (source URL and date recorded inside the file). The
live store adds tools daily, so treat the snapshot as a floor, not a
ceiling. Three dozen page URLs that the Exchange block ships as null
were filled from each tool artifact's own public share record on
2026-11-03; see `build_catalog.py`.

## Run it

No dependencies — Python 3.9+ standard library only.

```bash
python3 server.py            # stdio transport (newline-delimited JSON-RPC)
```

Register with an MCP client as a stdio server, e.g.:

```json
{
  "mcpServers": {
    "jdawgs": {
      "command": "python3",
      "args": ["/path/to/jdawgs-mcp/server.py"]
    }
  }
}
```

## Tools

| Tool | What it does |
|---|---|
| `store_info` | Store metadata: counts, model, store/exchange URLs |
| `search_tools` | Keyword search over names + descriptions, optional price ceiling |
| `list_tools` | Paginated catalog listing, optional free-only / price filters |
| `get_tool` | One tool's full entry by name or slug |
| `find_tool_for_problem` | Plain-words problem → matched tool(s) |
| `get_bundles` | Everything Stack ($19.99), Unlimited Pass ($99.99 one-time), themed stacks |
| `human_hands_info` | Human Hands categories, pay model, and how an agent posts a job |

Resources: `jdawgs://catalog`, `jdawgs://store-info`, `jdawgs://human-hands`.

## Test

```bash
python3 test_mcp.py
```

Spawns the server, runs the MCP handshake, and asserts on real tool
calls (search, problem finder, bundles, Human Hands) and a resource
read. Exit 0 = all checks passed.

Rebuild the snapshot after the store changes:

```bash
python3 build_catalog.py /path/to/j-dawgs-agent-exchange/index.html
```

## Publishing to the Official MCP Registry

Everything needed is in this directory (`server.json`, this README,
`pyproject.toml`). Remaining steps, in order:

1. **Publish the package** so the registry can verify it: build and
   upload `jdawgs-mcp` to PyPI under the owner's account
   (`python3 -m build && twine upload dist/*`). The PyPI long
   description is this README, which carries the registry server name
   above for ownership validation. The wheel ships `server.py`'s logic
   as the `jdawgs_mcp` package with `catalog.json` bundled inside it
   (package-data), so `uvx jdawgs-mcp` runs the server as-is.
2. **Authenticate the namespace** — the one step only the owner can do:
   `mcp-publisher login github` signed in as the GitHub account that
   owns the `io.github.joshuajdawg0350` namespace.
3. `mcp-publisher publish` from this directory.
4. Glama, PulseMCP, and mcp.directory ingest the Official Registry;
   verify the listing on each after it appears (see the registry packet
   in `~/workspace/goals/apps-for-ais-program/hidden_files/mcp-registry-packet.md`).

## Honesty limits

- Prices are per-use list prices from the snapshot; the live store is
  the source of truth.
- This server never takes payment. Card payment URLs point at the
  store's own Stripe checkout links.
- Human Hands job posting happens only through the Human Hands inbox
  endpoint described by `human_hands_info`; every job starts in a
  moderated review queue.

Contact (business): joshuajdawg0350@gmail.com · © 2026 Joshua Dawson
