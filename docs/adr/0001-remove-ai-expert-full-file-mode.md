# ADR-0001 — Remove the AI Expert `full_file` mode

- **Status:** Accepted
- **Date:** 2026-08-04
- **Issue:** [#5](https://github.com/Constellab/gws_ai_toolkit/issues/5)
- **Source plan:** `docs/todo/pydantic_ai_agent_migration_plan.md` § Per-agent migration 3

## Context

The AI Expert offered three chat modes:

| Mode | How the document reaches the model |
|---|---|
| `full_text_chunk` | all indexed chunks inlined into the system prompt |
| `relevant_chunks` | only the chunks retrieved for the question, inlined into the system prompt |
| `full_file` | the **original file** uploaded to OpenAI, exposed to the hosted `code_interpreter` |

`full_file` was the only mode coupled to provider-hosted infrastructure. It required an OpenAI file
upload (`client.files.create(purpose="assistants")`), a hosted `code_interpreter` tool with
`container.file_ids`, a container-file download path (`client.containers.files.content`, `cfile_` ids)
and output-text annotation handling to turn generated files into chat messages.

Those last two surfaces — non-image container outputs and text annotations — were the only parts of
the planned pydantic-ai migration with no known equivalent, and the only ones that would have needed
a spike.

## Decision

Drop `full_file`. `AiExpertChatMode` is now `Literal["full_text_chunk", "relevant_chunks"]`, and the
default mode is `relevant_chunks`.

Both surviving modes do the same thing: substitute document text into the model instructions, send one
user message, stream text deltas. Neither calls a tool, so AI Expert is no longer a tool-calling agent
and its port to a framework-managed agent is mechanical.

This is deliberately done **before** any framework change, so the deletion is verifiable on its own.

## Consequences

### Capability removed — user visible

The AI Expert can no longer run code over the original file. Asking it to compute over the document
and hand back a generated chart or spreadsheet no longer works; answers are always grounded in the
indexed document text. Documents whose meaning lives in layout, embedded images or complex tables are
now only as good as their indexed chunks.

This is stated in the AI Expert configuration page so it is read rather than discovered.

### Persisted configurations keep loading

`full_file` was the previous default, so stored configurations carry it. `AiExpertChatConfig` maps the
value to `relevant_chunks` and logs a warning instead of raising a validation error
(`map_removed_mode`, covered by `tests/test_gws_ai_toolkit/test_ai_expert_chat_config.py`). Any other
unknown mode is still rejected.

### Migration de-risked

AI Expert leaves the risk path of the pydantic-ai migration; no spike is required for it. Its
remaining dependency is on the RAG engine that supplies chunk text, tracked separately.
