# Agent migration — hand-rolled OpenAI loops → pydantic-ai

> Paired with [rag_embedded_stack_implementation_plan.md](rag_embedded_stack_implementation_plan.md).
> Decided August 2026. The knowledge-base chat is built on the migrated base, and AI Expert in turn
> needs the new engine — so the two plans **interleave**; see *Ordering* below for the combined
> sequence. Move to `docs/done/` once implemented.

## Goal

Delete every hand-written OpenAI agent loop in this brick and run all agents on **pydantic-ai**.
Today each agent re-implements streaming, tool dispatch, history and error handling against the
OpenAI Responses API. That is three copies of the same loop, provider-locked, with no test seam.

Secondary, and the reason this blocks the RAG work: the knowledge-base chat needs a tool-calling
agent. Building it on pydantic-ai while three other agents stay hand-rolled would leave two
paradigms in the brick permanently. **Migrating first means the RAG chat is written once, on the
same base as everything else.**

## What exists today (verified against code)

| Component | File | Uses |
|---|---|---|
| `BaseFunctionAgentAi` | `core/agents/base_function_agent_ai.py` | `openai_client.responses.stream(...)` (`:217`), `previous_response_id` (`:222`), `_handle_function_call`, `replay_events` (`:345`), `call_sub_agent` (`:381`) |
| Env agent | `core/agents/env_agent_ai.py`, `env_generator_ai.py` | `{"type": "function"}` tools (`:107`), code generation + execution |
| Table agent | `core/agents/table/table_agent_ai_service.py` | function tools over a DataFrame |
| AI Expert | `models/chat/conversation/ai_expert_chat_conversation.py` | `client.responses.stream(...)` with `instructions` + `temperature` + `previous_response_id` (`:149-158`). **`full_file` mode is being removed** — see below |

**The seam is already in the right place.** `models/chat/conversation/base_chat_conversation.py`
imports **no Reflex** — only stdlib, `gws_core` and brick models. Its single abstract method is
`_call_ai_chat(user_message) -> Generator[ChatMessage]`, with `build_current_message()` /
`close_current_message()` helpers. Reflex coupling lives one layer up, in
`apps/rag_app/.../chat_base/conversation_chat_state_base.py`. So a migrated agent stays drivable
from both the UI and (later) an HTTP route with no duplicated loop.

## Decisions (settled)

1. **All four agents migrate** — table, env, AI Expert, plus the new knowledge-base chat. No
   hand-rolled loop survives; `base_function_agent_ai.py` and `base_function_agent_events.py` are
   deleted at the end.
2. **Client-side conversation history everywhere.** pydantic-ai `list[ModelMessage]`, persisted in
   the existing chat tables and replayed on restore. **`previous_response_id` /
   `openai_conversation_id` are not used.**
3. **Tool turns are persisted.** A restored conversation must show the model what it already
   retrieved or executed.
4. **`provider:model` strings** on every configuration surface, aligned with
   `gws_core/docs/todo/refactor/ai_agent_chat_plan.md`. `openai:*` is the only value exercised in
   V1; other providers are a config change, not a code change.

### Why client-side, not OpenAI server-side state

pydantic-ai's settings for server-side state are named `openai_previous_response_id` and
`openai_conversation_id` — the prefix is the point. **No equivalent exists for Anthropic or
Google**: the Claude API is stateless ("send the full conversation history each time"), with prompt
caching (~0.1× input on the cached prefix) as the cost answer rather than a conversation handle.
pydantic-ai's own model is a provider-independent message list, and its `conversation_id` is a
locally generated correlation id, not a provider handle.

So server-side state is not a portable option that we are declining — it is an OpenAI-only path.
Adopting it would re-lock the brick to OpenAI in the one place hardest to unwind, defeating the
reason for adopting pydantic-ai at all.

**Accepted costs:** the full message list is resent each turn (mitigated by provider prompt
caching), and reasoning context is not carried across turns the way `previous_response_id` carried
it.

## Persisting tool turns — no migration needed

`ChatMessageModel` (`models/chat/chat_message_model.py`) already has:

```
role     CharField(max_length=20)   # typed Literal["user", "assistant"]
type     CharField(max_length=20)
data     JSONField(null=True)
message  TextField(null=True)
```

Tool turns ride in `data` under two new `type` values — no new column, no new table, and both
values fit the 20-char limit:

| pydantic-ai part | `role` | `type` | `data` |
|---|---|---|---|
| `ToolCallPart` (on the model response) | `assistant` | `tool_call` | `{tool_name, args, tool_call_id}` |
| `ToolReturnPart` (on the following request) | `user` | `tool_result` | `{tool_name, content, tool_call_id}` |

`role` stays within its existing `Literal` — pydantic-ai puts tool calls on the assistant response
and tool returns on the user-side request, so no widening is required.

**Rendering rule:** these two types are history-only. The Reflex chat widget and the HTTP route
both skip them when building the visible transcript; they exist to rebuild `message_history`
faithfully. Restore maps rows → `ModelMessage` parts in `created_at` order.

## Per-agent migration

Each agent keeps its current public surface (constructor args, emitted `ChatMessage` sequence) so
its Reflex state and components need no change beyond what the compiler forces.

### 1. Table agent — low risk, do first

Plain function tools over a DataFrame; no hosted tools, no file plumbing. Port to
`Agent(model=..., instructions=..., deps_type=...)` with `@agent.tool` functions. This is the
reference implementation the other two follow, and the place to settle the streaming → `ChatMessage`
adapter once.

### 2. Env agent — low risk

Same shape (function tools + iterative error feedback on generated code). `env_generator_ai.py`
follows. Its `call_sub_agent` usage becomes a nested `Agent` run.

### 3. AI Expert — `full_file` mode removed first, then a trivial port

**Decision (August 2026): drop the `full_file` mode.** `AiExpertChatMode` becomes
`Literal["full_text_chunk", "relevant_chunks"]`.

That single decision deletes AI Expert's entire hard-to-migrate surface:

| Removed with `full_file` | Where |
|---|---|
| `client.files.create(purpose="assistants")`, `openai_file_id` | `:191-210` |
| hosted `code_interpreter` + `container.file_ids` | `:122-124` |
| `client.containers.files.content(...)` / `cfile_` downloads | `:285-314` |
| `_handle_output_text_annotation_added` + the `response.output_text.annotation.added` branch | `:165-168`, `:266` |

Both **non-image container outputs** and **text annotations** — previously the two unproven gaps
requiring a spike — existed *only* to serve code-interpreter output files. **No spike is needed**, and
AI Expert stops being the risky agent.

What remains, in both surviving modes: substitute the document text into `instructions`, send one user
message, stream text deltas. `tools = []` in both branches — AI Expert is not a tool-calling agent at
all, so its port is `Agent(model, instructions=...)` plus a stream. `temperature` (default 0.7)
becomes a pydantic-ai model setting.

**Migration detail:** the current default is `mode = "full_file"`, so a persisted config carrying it
must be read as `relevant_chunks` with a log line — never an error on load.

**It depends on the new engine.** Both surviving modes source their text from `BaseRagService`, which
is being deleted:

| Mode | Today | After |
|---|---|---|
| `relevant_chunks` | `rag_service.retrieve_chunks(dataset_id, query, top_k, document_ids=[id])` (`:237`) | `engine.retrieve(query, knowledge_base_ids, top_k, document_ids=[id])` — the engine needs the `document_ids` filter |
| `full_text_chunk` | `rag_service.get_document_chunks(dataset_id, document_id, page, limit)` (`:219`) | read the **document snapshot** directly — exact text, no chunk-boundary artefacts, no engine call |

Hence AI Expert is ported **after** the knowledge-base engine exists, in one pass that both migrates
the loop and repoints the text source. See the ordering below.

### 4. Knowledge-base chat

New, built directly on pydantic-ai — specified in
[rag_embedded_stack_implementation_plan.md](rag_embedded_stack_implementation_plan.md) §4.

## Dependencies

### Prerequisite: bump `openai` in gws_core

`pydantic-ai-slim[openai]` requires `openai>=2.45`; `bricks/gws_core/settings.json:98` pins
`2.2.0` — a real conflict. **Bump `openai` to the latest 2.x in gws_core**, run its
OpenAI-dependent tests (AI Expert-adjacent code paths use the Responses API), and release before or
with this work. Confirmed acceptable.

### `bricks/gws_ai_toolkit/settings.json`

Add `pydantic-ai-slim[openai]` and bump the `gws_core` dependency to the release carrying the
`openai` bump. **Re-verify the pin at implementation time**: the `2.17.0` version named in the
earlier draft predates the current API surface (docs now show `capabilities=[NativeTool(...)]`),
so pick the version that actually carries `CodeExecutionTool` + `UploadedFile` and pin that.
Add the `anthropic` / `google` extras only when a profile needs them.

## Ordering

The `full_file` removal takes AI Expert off the risk path, but its remaining modes depend on the new
engine — so the two plans interleave rather than running strictly back to back.

0. gws_core `openai` bump, released.
1. **Remove `full_file`** from AI Expert (delete the mode and everything in the table above; default
   becomes `relevant_chunks`). Done on the *existing* loop, before any framework change, so the
   deletion is verifiable on its own.
2. Table agent ported; streaming → `ChatMessage` adapter settled; tests green.
3. Env agent + env generator ported; tests green.
4. Tool-turn persistence (`tool_call` / `tool_result` types, restore mapping); tests green.
5. → **Knowledge-base engine and services**
   ([rag_embedded_stack_implementation_plan.md](rag_embedded_stack_implementation_plan.md) steps 1–2),
   including `retrieve(..., document_ids=...)`.
6. AI Expert ported **and repointed** at the engine/snapshot in one pass; tests green.
7. `base_function_agent_ai.py`, `base_function_agent_events.py` deleted; `ruff check --fix`; full
   suite. **No hand-rolled loop remains.**
8. → Knowledge-base chat and UI (embedded-stack plan steps 3 onward), on the migrated base.

Steps 1–4 are independent of the engine and can land as their own release.

## Verification

Run per file from the brick directory: `gws server test <file>` (not the full suite).

- `test_table_agent.py`, env-agent tests — existing tests must pass unchanged where the public
  surface is unchanged; use pydantic-ai `TestModel` / `FunctionModel` so no API calls are made.
- New: restore fidelity — a conversation with a tool call, persisted and restored, yields a
  `message_history` containing the tool call and its result.
- AI Expert: a persisted config with `mode = "full_file"` loads as `relevant_chunks` and logs, rather
  than raising.
- Manual: AI Expert end to end on a real document in both surviving modes — `relevant_chunks` against
  the engine with a `document_ids` filter, `full_text_chunk` from the snapshot.

## Risks

- ~~AI Expert's provider coupling~~ — removed by dropping `full_file`. The remaining risk is
  smaller and different: **users lose the code-interpreter capability** (asking the assistant to
  compute over the original file and hand back a generated chart or spreadsheet). That is a
  deliberate product decision, not a migration casualty, but it should be communicated rather than
  discovered.
- **The `openai` bump lands in another brick**, so this work is coupled to a gws_core release.
- **Two paradigms exist mid-migration** (steps 2–5). Accepted and time-bounded; the rule during
  that window is that no *new* hand-rolled loop is written.
- **pydantic-ai moves fast** (monthly majors). Pin explicitly, re-read the changelog on any bump,
  and keep provider-specific settings confined to the agent-construction helper.
