# MCP Fundamentals

*Last updated: 2026-08-29.*

---

## What MCP is

Model Context Protocol — a standard way to give AI agents access to external
tools, data, and workflows. Instead of hard-coding API calls into a prompt or
application, you build an MCP server that exposes capabilities, and any
MCP-compatible client (Claude Desktop, Claude Code, etc.) can use it.

The analogy: MCP is to AI agents what REST is to web services. A standard
interface so clients and servers can talk without knowing each other's internals.

---

## The three primitives

MCP has exactly three building blocks. Understanding who controls each one is
the key to knowing when to use which.

### Tools — controlled by the AI model

Functions the agent calls during a conversation to fetch data or take action.
The agent decides when to call them, with what arguments, and what to do with
the result.

Examples: `search_records`, `fetch_data`, `compute_summary`.

Think of tools as the agent's hands — it reaches out, does something, gets
a result back.

### Resources — controlled by the client

Read-only context that the client (Claude Desktop, etc.) loads before the
conversation starts and injects into the agent's context. The agent doesn't
call resources — the client loads them automatically.

Examples: a system prompt with instructions, a reference list of valid codes
or categories, a schema describing what data is available.

Think of resources as background reading the agent does before the conversation,
not something it actively requests mid-task.

**Why resources matter:** they give the agent upfront knowledge without burning
tool calls. The agent walks in already knowing the reference data, rather than
having to fetch it on every request.

### Prompts — controlled by the user

Pre-built workflow templates with named input fields. The user picks one and
fills in the parameters — the prompt then expands into a full message that kicks
off a tool chain.

In Claude Desktop: appears as a popup with fields to fill in. In Claude Code:
invoked as a slash command (`/mcp__server__prompt_name param=value`).

Example: a `summarise_report(date_range, region)` prompt that automatically
chains fetch → filter → summarise without the user having to know the call order.

Think of prompts as shortcuts for packaged workflows — a user doesn't have to
know the right call order; the prompt handles it.

---

## How they interact in a real request

```
User picks a prompt and fills in parameters
    ↓
Client has already loaded resources (instructions, reference data) into context
    ↓
Prompt expands into a full task description
    ↓
Agent calls tools in sequence to fulfil the task
    ↓
Agent synthesises results and responds
```

Resources front-loaded the agent's knowledge. The prompt handled the workflow.
The tools did the actual work.

---

## Claude Desktop vs Claude Code

| | Claude Desktop | Claude Code |
|---|---|---|
| Resources | Loaded automatically, available in context | Same |
| Tools | Agent calls them; visible in tool-call panel | Same |
| Prompts | Popup UI with named fields — user-friendly | Slash command: `/mcp__server__prompt param=value` — power-user |

The popup UX in Claude Desktop is why prompts are good for demos. Claude Code
is where you build and test — the experience is less polished but the same
underlying capability.

---

## Related

- [[mcp-fastmcp]] — which framework to use to build MCP servers in Python
- [[observability]] — how to add logging and tracing to an MCP server
