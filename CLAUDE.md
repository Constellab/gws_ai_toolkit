# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GWS AI Toolkit is a Constellab brick (library) developed by Gencovery that provides AI-driven tools for data analysis and visualization in the life sciences. It depends on the `gws_core` brick (version 0.16.1) and includes RAG (Retrieval Augmented Generation) implementations for Dify and RagFlow platforms.

## Key Commands

### Development Commands
- Start the server: `gws server run`
- Run specific unit test: `gws server test [TEST_FILE_NAME]` (without .py extension)
- Run all tests: `gws server test all`

### Configuration
- VSCode users can use predefined run configurations in `.vscode/launch.json`
- Project settings are defined in `settings.json` (Constellab brick configuration)

## Architecture

### Directory Structure
- `src/gws_ai_toolkit/rag/` - Main RAG implementations
  - `dify/` - Dify platform integration
  - `ragflow/` - RagFlow platform integration
- `tests/test_gws_ai_toolkit/` - Test files

### Core Components

#### Dify Integration (`src/gws_ai_toolkit/rag/dify/`)
- `dify_class.py` - Data models and DTOs for Dify API responses and requests
- `dify_service.py` - Main service class for Dify API interactions including:
  - Document upload/update to knowledge bases
  - Chunk retrieval with various search methods (semantic, keyword, hybrid, full-text)
  - Streaming chat functionality
  - Metadata management for documents
- `datahub_dify_*.py` - Constellab DataHub integration components
- `doc_expert_ai_page*.py` - UI pages for document expert functionality

#### RagFlow Integration (`src/gws_ai_toolkit/rag/ragflow/`)
- `ragflow_class.py` - Data models and DTOs for RagFlow API using the ragflow-sdk
- `ragflow_service.py` - Main service class wrapping the RagFlow SDK for:
  - Dataset/knowledge base management
  - Document upload/parsing
  - Chunk retrieval
  - Chat assistant creation and management
  - Session management with streaming chat
- `datahub_ragflow_*.py` - Constellab DataHub integration components
- `doc_expert_ai_page*.py` - UI pages for document expert functionality

### Service Pattern
Both Dify and RagFlow services follow a similar pattern:
- Use credential-based authentication via `from_credentials()` static methods
- Support streaming responses for chat functionality
- Implement comprehensive document and chunk management
- Return standardized response objects using BaseModelDTO

### Dependencies
- `gws_core` (v0.16.1) - Core Constellab functionality including BaseModelDTO, credentials, external API services
- `ragflow-sdk` (v0.20.3) - Official RagFlow Python SDK
- Standard libraries: `requests`, `json`, `typing`

## Development Notes

### Working with Services
- Both DifyService and RagFlowService can be instantiated from Constellab credentials
- Services handle HTTP requests/SDK calls and convert responses to standardized DTOs
- Error handling follows the pattern of raising RuntimeError with descriptive messages

### Testing
- Tests should be placed in `tests/test_gws_ai_toolkit/`
- Use the testdata directory referenced in settings.json: `${CURRENT_DIR}/tests/testdata`

### Constellab Integration
- This is a Constellab brick that integrates with the broader Constellab ecosystem
- DataHub resources and services provide integration points with the platform
- UI pages follow Constellab's page/state pattern for web interfaces