# ADR-0002 — Retire the AI Expert mode; fold it into Document Focus on Knowledge Base chat

- **Status:** Accepted
- **Date:** 2026-08-05

## Context

`ChatConversationMode` has four values: `RAG` (legacy, provider-hosted), `AI_EXPERT`, `AI_TABLE`
(separate standalone app, unaffected), and `KNOWLEDGE_BASE` (the tool-calling agent chat, built on
`BasePydanticAgentAi`).

`AI_EXPERT` is a full parallel stack: its own conversation class (`AiExpertChatConversation`), its own
agent (`AiExpertAgentAi`, which is *not* a tool-calling agent — `_get_tools()` returns `[]`), its own
routes (`/ai-expert`, `/ai-expert/[document_id]`, `/ai-expert/chat/[conversation_id]`), a document
browser page, and a mode-switcher chip linking it to legacy RAG chat.

After ADR-0001 removed the `full_file` sub-mode, and with `full_text_chunk` dropped in this change (see
Decision), AI Expert's only remaining behavior is: retrieve chunks with `document_ids=[the one
document]`. That is the same retrieval call `KnowledgeBaseAgentAi`'s `search_knowledge` tool already
makes, just hard-coded to exactly one document instead of a conversation-supplied list. There is no
capability left in AI Expert that isn't a special case of "search, restricted to some documents."

## Decision

Delete `AiExpertChatConversation`, `AiExpertAgentAi`, `AiExpertChatConfig`, the `/ai-expert*` routes,
the document browser page, and the RAG/AI-Expert mode-switcher chip (`conversation_mode_chip_switchable`
and its two call sites).

Replace the capability with **Document Focus** on `KNOWLEDGE_BASE` chat (see `CONTEXT.md`):

- A per-message list of focused document ids, stored the same way tool calls/table attachments already
  ride in `ChatMessageModel`'s JSON `data` field — no new column.
- App-enforced, not model-facing: when focus is non-empty, the app injects `document_ids` into the
  existing `search_knowledge` tool call. The model is never given a second tool to choose between, so
  scoping can't be skipped by a model choosing not to call it.
- Focus only reaches documents already inside the conversation's `RagChatProfile.knowledge_base_ids` —
  it narrows the profile's scope, never widens it.
- Two entry points: an in-chat "+" picker next to the composer (mirrors `ai_table`'s
  `table_selection_menu()`/`_table_list()`), which adds focus to the *current* conversation; and a
  knowledge-base document row action, "Focus in new chat" (replaces today's "Chat about this document"
  / `rx.redirect(f"/ai-expert/{document.id}")`), which opens a new `KNOWLEDGE_BASE` conversation using
  the first `RagChatProfile` containing that document's knowledge base, pre-focused on it. If no such
  profile exists, this action errors — no auto-creation for now.
- `full_text_chunk` (read a document's entire stored text verbatim, no retrieval) is dropped, not
  carried forward as an option gated on single-document focus. It doesn't generalize to N focused
  documents, and nothing suggests it was a deliberate user choice rather than a workaround.

Also, generalize legacy-mode handling rather than building a second implementation: `AI_EXPERT` becomes
a retired `ChatConversationMode` value, and both it and `RAG` now render through one generic legacy
view — messages read-only, composer disabled, no attempt to reconstruct mode-specific context — instead
of `RAG` keeping its own dedicated legacy path while `AI_EXPERT` gets a different one.

## Consequences

### Capability removed — user visible

There is no longer a way to read a document's full raw text verbatim into a prompt (only chunk
retrieval, scoped by focus). Existing AI Expert conversations become read-only history rendered by the
generic legacy view: which document the conversation was originally about is not shown, and no other
AI-Expert-specific context is reconstructed. No data is deleted — old `ChatConversation` rows with
`mode="ai_expert"` (in production since 2025-11-25) remain in the database and still appear, badged, in
the existing unified history sidebar — they just no longer have dedicated code rendering them.

### Simplifies the codebase going forward

One agent class (`KnowledgeBaseAgentAi`) and one set of live chat routes handle everything that isn't
legacy. Any future retired mode reuses the same generic legacy-restore path instead of growing a new
one.

### No DB migration required

`RAG` and `AI_EXPERT` stay as valid, legacy-flagged `ChatConversationMode` values purely for labeling
and routing existing rows into the generic legacy view. Document Focus needs no schema change: it rides
the existing per-message JSON `data` field, the same pattern already used for tool calls/results and
table attachments.
