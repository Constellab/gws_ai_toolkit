# Knowledge-base public API — Community-facing chat route

> Third of three documents. Depends on
> [rag_embedded_stack_implementation_plan.md](rag_embedded_stack_implementation_plan.md) (engine,
> `KnowledgeBase`, `RagChatProfile`) and
> [pydantic_ai_agent_migration_plan.md](pydantic_ai_agent_migration_plan.md) (the chat loop).
> Decided August 2026. Move to `docs/done/` once implemented.

## Why this exists

The Constellab Community chatbot is **already a lab-hosted RAG service**. Two facts from the code:

- `gws_ai_toolkit/rag/ragflow/ragflow_start_docker_compose.py:87-103` starts RAGFlow as a docker
  compose stack **inside a data lab**, registered with Constellab's `DockerService`.
- `gws_core/src/gws_core/community/community_user_service.py:24-28` calls
  `POST {community_api_url}/ragflow-chatbot/ask`; `community_dto.py:151` types the response. The
  Community backend fronts the chatbot and talks to the lab-hosted RAGFlow behind it.

So the "community instance" is not a new kind of deployment — it is **one lab that serves external
callers**. When RAGFlow is removed from this brick (see the embedded-stack plan), that lab needs a
replacement endpoint for the Community backend to call. Nothing in the brick exposes HTTP today:
there is no `APIRouter`, no `core_app` usage anywhere in `gws_ai_toolkit/src`.

The live contract to preserve: `message` + optional `session_id` → `answer`, `session_id`,
`references`. It is actively used — the workspace CLAUDE.md instructs developers to run
`gws community ask-chatbot` before writing code.

## Where the route lives

`gws_core/src/gws_core/lab/api_registry.py:124-157` provides the mechanism:

```python
kb_api = ApiRegistry.register_brick_api("gws_ai_toolkit")

@kb_api.post("/chat/ask")
def ask(...): ...
```

The sub-app is mounted at **`/brick/gws_ai_toolkit/`**, and `ApiRegistry` attaches the lab's CORS
policy and security headers. Declare the CORS policy on registration rather than adding middleware
to the returned app — per that module's own guidance.

**The route runs in the server process**, not the Reflex app process. This is only well-defined
because the engine uses `fcntl.flock` around LanceDB access rather than the "writes only in the app
process" rule of the earlier draft: a server-process reader is a first-class case.

## Authorisation — the publish token

`AuthorizationService` offers **user access token, app token, share link, unique code**. There is no
service-to-service or API-key mode, and the Community backend is exactly that missing case.

**Decision: publishing is a property of a chat profile, and the token is the scope.**

```
RagChatProfile
├── is_published      BooleanField(default=False)
├── publish_token      CharField(max_length=64, null=True, unique=True, index=True)
└── published_at       DateTimeField(null=True)
```

- **Publishing** a profile mints a random token; **un-publishing** clears it and revokes access
  immediately. Both are explicit admin actions with an audit trail via `last_modified_by`.
- The route authenticates the bearer token and **derives the profile from it**. No caller-supplied
  profile or knowledge-base id is ever trusted.
- Community stores one token per chatbot.

### Why the scope rule is load-bearing, not defensive

V1 has **no per-document access filtering** — every chunk carries `access_scope = "*"` (see the
embedded-stack plan §Access control). The publish token is therefore the *only* boundary between an
external caller and a lab's documents. A route accepting an arbitrary `chat_profile_id` would expose
**every knowledge base in that lab** to anyone who could reach it. Deriving scope from the token
makes that impossible by construction rather than by validation.

Two consequences to keep in view:

- A published profile's bound knowledge bases are effectively **world-readable to whoever holds the
  token**. The publish UI must say so in those terms, and publishing should be restricted to lab
  admins (see *Open items*).
- Tokens are credentials: never logged, shown once at mint time, rotatable by re-publishing.

## Endpoints

Both shapes drain the same `_call_ai_chat` generator, so there is one implementation and no second
chat loop. Field names match today's contract so `CommunityUserService.ask_ragflow_chatbot` becomes
a rename rather than a rewrite.

### `POST /brick/gws_ai_toolkit/chat/ask` — non-streaming

For the CLI (`gws community ask-chatbot`) and any server-side caller.

```
Authorization: Bearer <publish_token>

{ "message": "...", "session_id": "<conversation id>" | null }
→
{ "answer": "...", "session_id": "...", "references": [ RagChatSource, ... ] }
```

### `POST /brick/gws_ai_toolkit/chat/stream` — SSE

For the Community website chat. Without it, every question shows a multi-second blank pause — the
same UX problem the Reflex app streams to avoid.

Events mirror the generator: text deltas, then a terminal event carrying `session_id` and
`references`. Errors become a typed error event, never a partial answer presented as complete.

### Mapping to existing concepts

| Contract field | Brick concept |
|---|---|
| `session_id` | `ChatConversation.id` (`mode = "knowledge_base"`, `configuration = {"chat_profile_id": ...}`) |
| `answer` | final assistant `ChatMessageText` |
| `references` | `RagChatSource` list — already the DTO `ChatMessageSourceModel` persists and the client renders |

`session_id = null` creates a conversation; a supplied `session_id` must belong to the token's
profile or the request is rejected. **Do not** let a token read another profile's conversations.

### Conversation ownership

`ChatConversation.user` is a non-null FK. External callers have no lab user, so published profiles
attribute conversations to a dedicated technical user created at publish time. This keeps history
listable and deletable per profile without weakening the token scope.

## Rate limiting and abuse

A published endpoint is reachable by anything holding the token, and every call costs an embedding
plus an LLM completion. V1 ships the minimum that prevents a token leak becoming an unbounded bill:

- Per-token request cap per window, rejecting with `429` when exceeded.
- Maximum `message` length, and a cap on conversation turns replayed per request.

Neither is sophisticated; both are cheap and the alternative is an unmetered spend path.

## Community-side work (not in this brick)

Landing this endpoint does **not** complete the migration. The Community backend must:

1. Store the publish token for its chatbot.
2. Repoint `/ragflow-chatbot/ask` at the new lab route (or expose a new path and migrate callers).
3. Adopt the SSE endpoint for the website chat.

`gws_core`'s `CommunityUserService.ask_ragflow_chatbot` and `community_dto.py` then get renamed off
"ragflow". **This is a different codebase and release train** — sequence it explicitly with that
team; it is the one part of this refactor that cannot land unilaterally.

## Verification

- `test_knowledge_base_api.py` — unpublished profile rejects; wrong token rejects; valid token
  resolves exactly its own profile; a `session_id` from another profile is rejected; un-publishing
  revokes immediately.
- Streaming: delta sequence then terminal event with references; error path emits an error event.
- Contract: response JSON matches the field names `gws_core`'s client expects.
- Manual: `gws community ask-chatbot` equivalent against a locally published profile.

## Open items

- **Who may publish?** There is no permission model, so as specified any lab user with app access
  could publish a knowledge base to the world. Restricting publish to lab admins is the intended
  answer and needs confirming against `UserGroup` (a flat SYSUSER < ADMIN < USER hierarchy).
- **Token transport to Community**: how the token reaches the Community backend's configuration, and
  who rotates it.
- Whether the Community website needs multiple published profiles (product docs vs developer docs)
  or one.
