# Vendored from the ESA EVE MCP tool registry

`gdacs.py` is `servers/gdacs/server.py` from https://github.com/eve-esa/mcp-tool-registry (commit 69bfcde),
Apache License 2.0, funded by ESA Φ-lab. Two mechanical changes so it runs under the `fastmcp` package: the
import line, and the `FastMCP` constructor without host and port. It provides `search_gdacs_events`.
