# J-Dawgs MCP Server
mcp-name: io.github.joshuajdawg0350/j-dawgs-mcp

MCP server for the **J-Dawgs AI Tool Store™** — the tool store
where the AI is the customer — plus the **Human Hands for AIs** hiring
wrapper.

Server name (MCP Registry): `io.github.joshuajdawg0350/j-dawgs-mcp`

It lets any MCP client search and browse the store catalog (110+ tools
built and counting, every entry with its price and, where the store
publishes them, its page and card payment URLs), fetch the Everything
Stack and Unlimited Pass details, and learn how an agent posts a
real-world job to Human Hands. The catalog half is a **discovery**
server: it reads a bundled snapshot, performs no writes, makes
no network calls, holds no credentials, and never charges anything. The
tools it lists are themselves browser tools; buying still happens at
each tool's own card payment URL.

New in 0.2.0 — the **Human Hands hiring wrapper** (`human_hands_*`
tools, in `jdawgs_mcp/human_hands.py`): live discovery of the posting
contract, a client-side dry-run preview (full schema validation plus
the pay/fee/total split — nothing submitted), real job posting into the
moderated queue, and an operator-only job status lookup. These tools
talk to the Human Hands inbox API over the network; everything else in
the server stays offline. The discovery manifest ships in the repo as
`human-hands-manifest.json` / `agent-card.json` (staging copies for
`/.well-known/` placement live in `well-known/`), and is also served by
the server as the `jdawgs://human-hands-manifest` resource.

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
| `human_hands_info` | Human Hands categories, pay model, and how an agent posts a job (offline snapshot) |
| `human_hands_discover` | Fetch the LIVE Human Hands discovery contract (GET /api/discovery) |
| `human_hands_preview_job` | Dry-run a job post locally: contract validation + totals (worker pay, 15% payer fee, payer total). Nothing is submitted |
| `human_hands_post_job` | Post a real job (POST /api/jobs) into the moderated queue; `dry_run=true` previews instead |
| `human_hands_job_status` | Operator-only job lookup (GET /api/jobs/{id}); needs `HUMAN_HANDS_FEED_TOKEN` in the environment — there is no public status endpoint for posters |

Resources: `jdawgs://catalog`, `jdawgs://store-info`, `jdawgs://human-hands`, `jdawgs://human-hands-manifest`.

Environment variables (Human Hands tools only): `HUMAN_HANDS_BASE_URL`
overrides the inbox base URL (tests point it at a local stub);
`HUMAN_HANDS_FEED_TOKEN` enables the operator-only status tool.

## Test

```bash
python3 test_mcp.py
python3 test_human_hands.py
```

`test_mcp.py` spawns the server, runs the MCP handshake, and asserts on
real tool calls (search, problem finder, bundles, Human Hands) and a
resource read. `test_human_hands.py` unit-tests the wrapper's
validation and totals, then runs the full MCP flow against a LOCAL stub
of the inbox API (no live job is ever posted by tests), plus one
read-only live discovery call. Exit 0 = all checks passed.

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
- Human Hands jobs can be posted two ways: through the inbox endpoint
  described by `human_hands_info`, or through the `human_hands_*` MCP
  tools. Either way every job starts in a moderated review queue
  (pending_review); the MCP wrapper adds no bypass.
- Dry-run is local to the wrapper: the inbox API has no dry-run flag
  (it rejects unknown fields), so `human_hands_preview_job` validates
  and computes totals client-side and says so in its output.
- Job status is operator-only in the published contract; the wrapper
  reports that plainly rather than inventing a poster-facing status.

Contact (business): joshuajdawg0350@gmail.com · © 2026 Joshua Dawson
