# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository. All path are relative to location of this file.

## Project Overview

GWS AI Toolkit is a Constellab brick (library) developed by Gencovery that provides AI-driven tools for data analysis and visualization in the life sciences. It depends on the `gws_core` brick (version 0.16.1) and includes RAG (Retrieval Augmented Generation) implementations for Dify and RagFlow platforms, plus a standalone Reflex-based RAG application.

## Key Commands

### Development Commands
- Start the server: `gws server run`
- Run specific unit test: `gws server test [TEST_FILE_NAME]` (without .py extension)
- Run all tests: `gws server test all`

### RAG Application Development
- RAG app directory: `src/gws_ai_toolkit/rag/rag_app/_rag_app/`

#### Routes
- `/` - That chat page and the main entry point of the Reflex app
- `/config` - Configuration page

#### Start RAG app
- Run the RAG app locally: `gws reflex run-dev src/gws_ai_toolkit/rag/rag_app/_rag_app/dev_config.json` 
- The app is available once the following log is print : `Running app in dev mode{env_txt}, DO NOT USE IN PRODUCTION. You can access the app at {url}`
- It takes about 20 seconds for the app to be fully ready.
- If the port is not available, kill the command. Then kill the process with the command `./kill_port_processes.sh 8511 8512`. Try to rerun the app 10 seconds later. If still not available, stop process here and tell the user.
- Once actions finished (like taking a screenshot), you must kill the process that started the RAG app.

#### Take Screenshot
- To take a screen shot of the app, use the `xvfb-run python take_screenshot.py` (in root folder of project) script. 
- Optionally specify a route: `xvfb-run python take_screenshot.py --route [ROUTE]` like `/config`
- Default route is "/" if no route is specified
- It generates a screenshot `app_screenshot.png` (in root folder of project).

### Configuration
- Project settings are defined in `settings.json` (Constellab brick configuration)
- RAG app configuration is in `src/gws_ai_toolkit/rag/rag_app/_rag_app/rxconfig.py`

## Architecture

### Directory Structure
- `src/gws_ai_toolkit/rag/` - Main RAG implementations
  - `common/` - Shared base classes and utilities
  - `dify/` - Dify platform integration  
  - `ragflow/` - RagFlow platform integration
  - `rag_app/_rag_app/` - Standalone Reflex-based RAG application
  - `datahub_dify_app/` - DataHub integration app for Dify
- `tests/test_gws_ai_toolkit/` - Test files

### Core Components

#### Common RAG Infrastructure (`src/gws_ai_toolkit/rag/common/`)
- `base_rag_service.py` - Abstract base class defining the common interface for all RAG services
- `rag_models.py` - Shared data models (RagDocument, RagChunk, RagChatStreamResponse, etc.)
- `rag_service_factory.py` - Factory pattern for creating RAG service instances
- `rag_enums.py` - Common enumerations used across RAG services
- `datahub_rag_resource.py` - DataHub resource integration
- `rag_datahub_service.py` - Service for DataHub RAG operations

#### Service Architecture Pattern
All RAG services implement the `BaseRagService` abstract class with these key methods:
- **Document Management**: `upload_document_and_parse()`, `update_document_and_parse()`, `delete_document()`, `get_all_documents()`
- **Chunk Retrieval**: `retrieve_chunks()` for semantic/keyword search
- **Chat Interface**: `chat_stream()` for streaming conversational AI
- **Factory Creation**: `from_credentials()` for credential-based instantiation

#### Dify Integration (`src/gws_ai_toolkit/rag/dify/`)
- `dify_service.py` - Direct Dify API implementation with HTTP requests
- `rag_dify_service.py` - Wrapper implementing BaseRagService interface
- `dify_class.py` - Data models and DTOs for Dify API responses
- `dify_send_file_to_knownledge_base.py` - File upload operations

#### RagFlow Integration (`src/gws_ai_toolkit/rag/ragflow/`)
- `ragflow_service.py` - Direct RagFlow SDK wrapper implementation  
- `rag_ragflow_service.py` - Wrapper implementing BaseRagService interface
- `ragflow_class.py` - Data models using ragflow-sdk types
- `ragflow_send_file_to_dataset.py` - File upload operations

#### RAG Application (`src/gws_ai_toolkit/rag/rag_app/_rag_app/`)
Standalone Reflex web application with:
- **Pages**: `pages/chat_page.py` (main interface), `pages/config_page.py` (admin)
- **Components**: Modular UI components in `components/` (chat interface, configuration panels)
- **State Management**: `states/chat_state.py`, `states/main_state.py` for application state
- **Integration**: Uses GWS Reflex base framework with authentication and theming

### Dependencies
- `gws_core` (v0.16.1) - Core Constellab functionality including BaseModelDTO, credentials, external API services
- `ragflow-sdk` (v0.20.3) - Official RagFlow Python SDK
- `reflex` (v0.8.2) - Web framework for the RAG application
- Standard libraries: `requests`, `json`, `typing`

## Development Notes

### Working with RAG Services
- All services implement the common `BaseRagService` interface for consistency
- Use `RagServiceFactory` to create service instances from configuration
- Services handle credential management through Constellab's credential system
- Error handling follows the pattern of raising RuntimeError with descriptive messages
- All responses use standardized DTOs (RagDocument, RagChunk, etc.)

### RAG Application Development
- The RAG app is a separate Reflex application that can run standalone
- Requires GWS environment variables for integration (GWS_REFLEX_*)
- Uses component-based architecture with separate state management
- Chat interface supports streaming responses and source citation
- Configuration page allows management of RAG resources and synchronization

### Testing
- Tests should be placed in `tests/test_gws_ai_toolkit/`
- Use the testdata directory referenced in settings.json: `${CURRENT_DIR}/tests/testdata`
- Test both individual service implementations and the common interface

### Constellab Integration
- This is a Constellab brick that integrates with the broader Constellab ecosystem
- DataHub resources and services provide integration points with the platform
- RAG services can be used both programmatically and through the web interface
- Authentication and authorization handled through Constellab's credential system