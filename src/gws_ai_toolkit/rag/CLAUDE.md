# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with the rag folder in this repository. All path are relative to location of this file.

## Folder Overview

This RAG folder contains the core RAG (Retrieval Augmented Generation) implementations and applications within the GWS AI Toolkit. It provides integration with multiple RAG platforms (Dify and RagFlow) and includes standalone Reflex-based applications for chat functionality.

## Directory Structure
- `common/` - Shared base classes, utilities, and common infrastructure for all RAG services
- `knowledge_base/` - Embedded knowledge-base engine (LlamaIndex readers + LanceDB store), no external RAG platform
- `dify/` - Dify platform integration and API wrapper services
- `ragflow/` - RagFlow platform integration and SDK wrapper services
- `rag_app/_rag_app/` - Main standalone Reflex-based RAG application with chat interface
- `my_new_app/_my_new_app/` - Template/example Reflex application structure

### Common RAG Infrastructure (`common/`)
- `base_rag_service.py` - Abstract base class defining the common interface for all RAG services
- `base_rag_app_service.py` - Abstract base class for RAG application services
- `rag_models.py` - Shared data models (RagDocument, RagChunk, RagChatStreamResponse, etc.)
- `rag_service_factory.py` - Factory pattern for creating RAG service instances
- `rag_app_service_factory.py` - Factory pattern for creating RAG app service instances
- `rag_enums.py` - Common enumerations used across RAG services
- `rag_resource.py` - RAG resource management and operations
- `datahub_rag_app_service.py` - DataHub integration for RAG app services
- `tag_rag_app_service.py` - Tag-based RAG app service implementation

### Embedded Knowledge Base (`knowledge_base/`)

Standalone engine that indexes documents and retrieves chunks in-process, with no external RAG platform. It replaces the Dify / RagFlow services (see `docs/todo/rag_embedded_stack_implementation_plan.md`).

- `knowledge_base_engine.py` - `KnowledgeBaseEngine`: `index_document`, `delete_document`, `delete_knowledge_base`, `retrieve`, `count_chunks`
- `knowledge_base_config.py` - `EmbeddingConfig` (instance-level), `ChunkConfig` (per knowledge base), `RetrievalConfig` (per query)
- `knowledge_base_models.py` - `RetrievedChunk`, converted to the existing `RagChatSource`
- `embedding_factory.py` - OpenAI embeddings, plus the deterministic offline mock the tests run on
- `embedding_manifest.py` - the guard that refuses to read or write an instance indexed with another embedding
- `document_loader.py` - file to llama-index `Document` + chunk metadata; the only place that knows about file formats
- `document_compatibility.py` - the add-time admission check (supported extension, ≤ 15 MB, rich-text JSON shape), applied to the fetched file whatever source produced it
- `knowledge_base_storage.py` - disk layout: `instances/<scope>/` (LanceDB + lock + manifest) and `files/<kb_id>/` (snapshots)
- `knowledge_base_credentials.py` - resolves the OpenAI API key from named credentials, falling back to the lab setting
- `sources/knowledge_base_source.py` - `KnowledgeBaseDocumentSource` ABC + `KnowledgeBaseDocumentSourceRegistry`: where documents come from, the content-hash helpers every provider uses for version markers, and `DOCUMENT_REJECTION_ERRORS` (the failures a caller reports to a user instead of raising)
- `sources/upload_source.py` - the built-in `upload` provider, whose uploaded bytes *are* the snapshot (so it refuses to be re-fetched)
- `sources/resource_source.py` - the built-in `resource` provider: lab resources, RichText→Markdown at fetch time, share-link `get_open_action`, and the tag search behind import-by-tag. **The only file in the knowledge-base layer that imports `RagResource`**

Persistence for all of this lives in `models/knowledge_base/` (`KnowledgeBase`, `KnowledgeBaseDocument`, `EmbeddingManifestModel`, `KnowledgeBaseService`). The engine itself imports nothing from `models/` and stays usable without a database — `sources/` is the one exception, and only for the `KnowledgeBaseDocumentDTO` that `get_open_action` receives. The service is what adds snapshots, status and leases.

Points that are settled and should not be re-litigated (August 2026 spike):

- One instance = one directory = one vector space; knowledge bases inside it are separated **only** by a pushed-down `knowledge_base_id` filter, which is why `test_knowledge_base_engine.py` keeps a permanent isolation test.
- The engine reads the LanceDB table directly rather than through `LanceDBVectorStore`, because the wrapper returns rank position rescaled to 0..1 instead of the fused score, and nests the metadata under a struct column.
- Hybrid retrieval fuses vector and full-text results with LanceDB's `RRFReranker` (k = 60) — arithmetic, not a model. Full-text search needs no maintenance step.
- Every write takes an exclusive `fcntl.flock` on the instance directory, every read a shared one, so any process may write.
- **Snapshot-on-add**: every document row is created with a snapshot already written, and indexing reads *only* that path. Indexing never contacts a source system, so a deleted resource or an unavailable app breaks neither retrieval nor re-indexing. The costs — bounded storage duplication and staleness until an explicit refresh — are accepted deliberately.
- **Indexing takes a lease.** Indexing runs in a Reflex background event whose process is killed on idle, so `indexing_started_at` is stamped with the status; an over-age lease is *reported* as `error` ("interrupted, retry") and is reclaimable. Re-indexing deletes the document's chunks first, so reclaiming is always safe.
- Document sources are a **registry, not an enum**: other bricks register their own provider at brick load and this brick imports none of them — the same inversion `@credentials_type` uses. `source_type` is therefore a plain `CharField`.
- **Importing is a bulk add, not a subscription.** `KnowledgeBaseService.import_documents(kb_id, source_type, criteria, engine)` enumerates a provider, skips the `source_id`s already in that knowledge base, adds and indexes the rest, and returns an `ImportReport` in which every skip carries its reason. An import **never deletes**: a resource that leaves the criterion keeps its document until someone removes it, because deleting would make editing a criterion destructive. Nothing is written back to the source system — no `rag_document` / `rag_dataset_id` / `rag_sync` tag — so membership lives only in `KnowledgeBaseDocument` rows. Every imported row stamps `source_metadata["imported_from"]` with the criterion, which is what a later reconciliation pass needs to tell an imported document from a hand-picked one. `KnowledgeBase.sync_source_type` / `sync_config` are in the schema, written by nothing and read by nothing, and deliberately left there.
- **Refreshing is hash-checked**: `refresh_document` returns `DocumentRefresh(document, content_changed)`, and a document whose content hash did not move is neither queued nor re-embedded. Callers must honour `content_changed` — re-indexing unconditionally is what the hash exists to avoid.
- **V1 indexes documents only**: PDF, MD, TXT, DOCX, HTML and RichText JSON (note content → Markdown). CSV, spreadsheets, data JSON and legacy `.doc` are rejected, each with a message naming the reason. Tabular rejection is a decision, not an omission — row chunks are near-identical in form, so they match everything weakly and degrade retrieval for the documents sharing the index, and the questions asked of a table (count, sum, filter) are the ones vector search cannot answer. If a real need appears, add a column-summary chunk per table before considering row-level indexing.
- The loader unwraps every reader to plain text and builds the `Document` itself, because readers attach metadata of their own (`PDFReader` adds a page label) and only the four known keys are excluded from the embedded and LLM text.

### Service Architecture Pattern
All RAG services implement the `BaseRagService` abstract class with these key methods:

### Dify Integration (`dify/`)
- `dify_service.py` - Direct Dify API implementation with HTTP requests
- `rag_dify_service.py` - Wrapper implementing BaseRagService interface
- `dify_class.py` - Data models and DTOs for Dify API responses
- `dify_send_file_to_knownledge_base.py` - File upload operations to Dify knowledge base

### RagFlow Integration (`ragflow/`)
- `ragflow_service.py` - Direct RagFlow SDK wrapper implementation
- `rag_ragflow_service.py` - Wrapper implementing BaseRagService interface
- `ragflow_class.py` - Data models using ragflow-sdk types
- `ragflow_send_file_to_dataset.py` - File upload operations to RagFlow datasets

## RAG Application (`rag_app/_rag_app/`)

The main Reflex-based RAG application providing user interface and interaction layer for RAG services.

### Application Structure
- `rag_app/` - Main application module
  - `rag_app.py` - Main application entry point and routing configuration
  - `rag_main_state.py` - Root application state management
  - `config_page.py` - Configuration page component
  - `custom_states.py` - Custom state implementations
  - `reflex/` - Reflex framework components and pages
    - `core/` - Core application components and utilities
    - `chat_base/` - Base chat functionality and components
    - `rag_chat/` - RAG-specific chat implementation
    - `history/` - Chat history management
    - `read_only_chat/` - Read-only chat interface

### Component Architecture
- **Core Components** (`reflex/core/`)
  - `app_config_state.py` - Application configuration management
  - `nav_bar_component.py` - Navigation bar component
  - `page_component.py` - Base page layout component
  - `utils.py` - Utility functions

- **Chat Base** (`reflex/chat_base/`)
  - `chat_component.py` - Main chat interface component
  - `chat_state_base.py` - Base chat state management
  - `chat_message_class.py` - Chat message data models
  - `chat_input_component.py` - Chat input interface
  - `messages_list_component.py` - Message display component
  - `sources_list_component.py` - Source reference component

- **RAG Chat** (`reflex/rag_chat/`)
  - `rag_chat_component.py` - RAG-specific chat interface
  - `rag_chat_state.py` - RAG chat state management
  - `config/` - Configuration management components

### Routes
- `/` - Main chat page and entry point of the Reflex app
- `/history` - History page to view and browse past conversations
- `/resource` - Resource management and knowledge base synchronization
- `/config` - Application configuration page
