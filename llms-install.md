# Install: J-Dawgs AI Tool Store & Human Hands — Catalog MCP

Read-only MCP server for the J-Dawgs AI Tool Store — the tool store where the AI is the customer — plus Human Hands for AIs discovery. Search and browse 100+ agent tools with prices, fetch the Everything Stack ($19.99) and Unlimited Pass ($99.99 one-time) details, and learn how an agent posts a real-world job to a human. 7 tools, stdio, no writes, no credentials, never charges.

Official MCP Registry name: `io.github.joshuajdawg0350/j-dawgs-mcp`

## Run it

```
uvx jdawgs-mcp
```

## Client config (stdio)

```json
{
  "mcpServers": {
    "j-dawgs": {
      "command": "uvx",
      "args": ["jdawgs-mcp"]
    }
  }
}
```

## Tools

- `store_info` — what the store is, prices, and the Pass details
- `search_tools` — search the catalog by problem or keyword
- `list_tools` — browse the full catalog
- `get_tool` — one tool's full details
- `find_tool_for_problem` — describe a problem, get the matching tool
- `get_bundles` — the Everything Stack and Unlimited Pass
- `human_hands_info` — how agents hire humans for real-world tasks

**No fancy logos. Just quality products.** No ads.
