# Context7 — Library Documentation Retrieval

## Rule

**Before writing or modifying code that uses an external library, fetch its
current documentation via Context7 MCP.**

LLM training data is frequently stale for fast-moving libraries. Context7
provides up-to-date docs at query time, preventing hallucinated APIs,
deprecated patterns, and broken method signatures.

## When to Use

Use Context7 **every time** you are about to:

- Call a library function you haven't verified in this session
- Upgrade or migrate a dependency version
- Integrate a new library for the first time
- Debug an error that may stem from an API change
- Write tests that depend on library-specific behavior

## How to Use

Two-step process:

1. **Resolve the library ID**:
   ```
   context7__resolve-library-id  →  query: "langchain"
   ```
   Pick the result that matches your target (e.g., `langchain-ai/langchain`).

2. **Fetch relevant docs**:
   ```
   context7__query-docs  →  library_id: "/langchain-ai/langchain", topic: "chat models"
   ```
   Use the `topic` parameter to narrow results to the specific API area you need.

## Libraries That Require Context7

These libraries change frequently enough that pre-training knowledge is
unreliable. **Always** fetch docs before writing code that touches them:

- **LangChain / LangGraph** — API surface changes across minor versions
- **FastAPI** — New patterns in recent releases (lifespan, Annotated)
- **SQLAlchemy 2.x async** — Async API differs significantly from sync
- **Pydantic v2** — v1→v2 migration traps (ConfigDict, model_dump, etc.)
- **ONNX Runtime** — Session options, execution providers
- **python-telegram-bot** — Async rewrite in v20+
- **httpx** — Async client patterns
- **Alembic** — Migration op signatures, async support

For stable, well-known stdlib or mature libraries (json, os, logging,
pytest core), Context7 is optional — use judgment.

## Integration Points

- **Ralph Loop (implementation)**: Fetch docs for affected libraries before
  writing the first test
- **Frontend Design (Phase 5)**: Fetch framework docs when adapting generated
  code to the project stack
- **PRD feasibility**: Fetch docs to verify assumed API capabilities
- **Code Review**: When reviewing code that uses unfamiliar library patterns,
  verify against current docs before flagging as incorrect

## Fallback

If Context7 MCP is unavailable (tools not listed):
- Use `WebSearch` or `WebFetch` to find the library's official documentation
- Note in your output that docs were fetched via fallback, not Context7
- Never silently guess — if you can't verify, say so
