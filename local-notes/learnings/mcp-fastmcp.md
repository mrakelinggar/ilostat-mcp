# MCP — FastMCP vs Official SDK

*Learned while building ilostat-mcp. Last updated: 2026-08-29.*

---

## The two options

When building an MCP server in Python you have two packages:

**`fastmcp`** — standalone package by jlowin (independent, actively maintained).
Current version: v2. Install: `pip install fastmcp`.

**`mcp`** — the official Anthropic/ModelContextProtocol Python SDK. Also ships
a `FastMCP` class (importable as `from mcp.server.fastmcp import FastMCP`),
but this is essentially the v1 API and hasn't kept pace with the standalone v2.

---

## Why we use standalone `fastmcp>=2.0,<3.0`

FastMCP v2 gives cleaner decorator-based registration, better type coercion,
and better error handling out of the box. The official SDK's `FastMCP` shim is
comparatively stale.

```python
# What we use
from fastmcp import FastMCP

mcp = FastMCP("ilostat-mcp")

@mcp.tool()
def get_countries() -> list[dict]:
    ...

@mcp.resource("ilostat://system-prompt")
def system_prompt() -> str:
    ...
```

No meaningful downside for a local-install MCP server.

---

## Important: version pinning

`fastmcp>=2.0` is too loose — if v3.0 ships with breaking changes the build
breaks silently. Always pin with an upper bound: `fastmcp>=2.0,<3.0`.

This applies to all dependencies, not just FastMCP. Upper bounds are a
production standard — see [[software-eng-breadth]].

---

## The history (why it's confusing)

FastMCP started as a third-party library that made MCP servers easier to build.
It was popular enough that Anthropic folded an early version of it into the
official `mcp` SDK. But the standalone package kept evolving as v2 while the
SDK version stayed at the v1 API. So today you have two things both called
"FastMCP" at different versions — confusing but real.

Rule of thumb: if you're starting a new MCP project in Python, use the
standalone `fastmcp` package, not the `mcp` SDK's built-in version.

---

## Dev tooling

FastMCP ships a dev server: `fastmcp dev src/your_server.py`

Opens the **MCP Inspector** in the browser — a UI at `localhost:5173` where
you can call tools directly, pass arguments, and see raw JSON responses.
No Claude required. Good for rapid iteration during development.

---

## Related

- [[mcp-fundamentals]] — what tools, resources, and prompts are
- [[observability]] — how to instrument an MCP server with logging and tracing
