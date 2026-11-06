# jdawgs-mcp — J-Dawgs MCP Server (stdio transport)
# Stdlib-only Python package: no dependencies to install, no network ports.
FROM python:3.12-slim

WORKDIR /app

# Copy just the package and its build metadata, then install it so the
# declared console script (jdawgs-mcp = jdawgs_mcp.server:main) exists.
COPY pyproject.toml README.md ./
COPY jdawgs_mcp/ ./jdawgs_mcp/
RUN pip install --no-cache-dir .

# Run unprivileged.
RUN useradd --create-home --uid 10001 appuser
USER appuser

# MCP over stdio: newline-delimited JSON-RPC on stdin/stdout.
ENTRYPOINT ["jdawgs-mcp"]
