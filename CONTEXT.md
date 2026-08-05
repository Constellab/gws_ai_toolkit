# GWS AI Toolkit — Domain Glossary

Domain vocabulary for the RAG/chat surface of this brick (`rag_app` and the models/services it sits on). General programming concepts and implementation details live in code and `docs/adr/`, not here.

## Language

**Document Focus**:
The set of documents (zero or more) a chat message is scoped to. When non-empty, the app restricts the knowledge-base search tool to just those document ids for that turn, narrowing — never widening — the conversation's normal knowledge-base scope. The UI carries it forward as the default for new messages until the user changes it, but each message still stores its own focus so history stays accurate turn-by-turn.
_Avoid_: AI Expert, document selection, scoped chat, document attachment

**Legacy Conversation**:
A `ChatConversation` whose `mode` has been retired (currently `RAG` and `AI_EXPERT`). Its historical messages render read-only through one generic legacy view, shared across every retired mode; it cannot be continued, and mode-specific context that existed only in the old experience (e.g. which single document a retired AI Expert chat was about) is not reconstructed.
_Avoid_: retired mode, archived chat, frozen conversation

**AI Expert** (retired):
Formerly a standalone chat mode limited to exactly one document, with its own agent, conversation class and routes. Its capability is superseded by Document Focus inside `KNOWLEDGE_BASE` chat. The name now only labels old conversations in history — do not use it for new behavior or code.
_Avoid_: AI Expert mode, AI Expert tool, AI Expert agent
