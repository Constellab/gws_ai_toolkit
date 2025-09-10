# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository. All path are relative to location of this file.

## Project Overview

GWS AI Toolkit is a Constellab brick (library) developed by Gencovery that provides AI-driven tools for data analysis and visualization in the life sciences. It depends on the `gws_core` brick (version 0.16.1) and includes RAG (Retrieval Augmented Generation) implementations for Dify and RagFlow platforms, plus a standalone Reflex-based RAG application.

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

## RAG Application
- RAG app directory: `src/gws_ai_toolkit/rag/rag_app/_rag_app/`
- This app is the main part of the repository. It is an app built using the Reflex framework and is responsible for providing the user interface and interaction layer for the RAG services (chat and configuration of the RAG).

### Dependencies
- `gws_core` (v0.16.1) - Core Constellab functionality including BaseModelDTO, credentials, external API services
- `reflex` (v0.8.2) - Web framework for the RAG application

### Routes
- `/` - That chat page and the main entry point of the Reflex app
- `/history` - History page to view and browse past conversations with scrollable sidebar and read-only chat display
- `/ai-expert/:resourceId` - Page to chat with an AI with the full document. For test use `/ai-expert/c9797bc487e911f0bde1323f673eb2db`
- `/resource` - Page to manage resources and sync with the knowledge base
- `/config` - Configuration page

### Development best practises
- Follow a modular architecture for components and pages
- Split the application into components. A component is defined by a folder containing the component and state file inside. Ex:
  - `chat/`
    - `chat/chat_component.py` (UI component)
    - `chat/chat_state.py` (state management)
- Use state management effectively to handle application state
- Keep UI components reusable and maintainable
- All the import from the rag_app that reference another file in the rag_app MUST be relative imports. Ex: `from .reflex import ai_expert_config_component` instead of `from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.reflex import ai_expert_config_component`
- Define the attributes, parameters and return types of functions, methods and classes using type hints
- for the `rx.button`, always set `cursor="pointer"` to have the pointer cursor on hover

### Start RAG app
- Run the RAG app locally: `gws reflex run-dev src/gws_ai_toolkit/rag/rag_app/_rag_app/dev_config.json` 
- The app is available once the following log is print : `Running app in dev mode{env_txt}, DO NOT USE IN PRODUCTION. You can access the app at {url}`
- Allow approximately 20 seconds for full initialization
- If you encounter port conflicts:
  - Terminate the current command
  - Run: ./kill_port_processes.sh 8511 8512
  - Wait 10 seconds before retrying
  - If issues persist, stop and inform the user
- During development:
  - You can keep the app running to leverage hot reloading
  - Code changes will automatically refresh
- Important: After completing all development work or capturing screenshots, terminate the RAG application process

### Test app in browser
- To take a screen shot of the app and check browser console, use the `xvfb-run python take_screenshot.py` (in root folder of project) script.
- When taking a screenshot, check the logs of app (backend) run process to see if there are any errors 
- Optionally specify a route: `xvfb-run python take_screenshot.py --route [ROUTE]` like `/config`
- Default route is "/" if no route is specified
- It generates a screenshot `app_screenshot.png` (in root folder of project)
- It generates a console logs file `console_logs.txt` (in root folder of project)