# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with the rag folder in this repository. All path are relative to location of this file.

## Folder Overview

This RAG folder contains the core RAG (Retrieval Augmented Generation) implementations and applications within the GWS AI Toolkit. It provides integration with multiple RAG platforms (Dify and RagFlow) and includes standalone Reflex-based applications for chat and AI expert functionality.

## Directory Structure
- `common/` - Shared base classes, utilities, and common infrastructure for all RAG services
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
  - `custom_ai_expert_component.py` - Custom AI expert interface component
  - `custom_ai_expert_state.py` - AI expert state management
  - `custom_states.py` - Custom state implementations
  - `reflex/` - Reflex framework components and pages
    - `core/` - Core application components and utilities
    - `chat_base/` - Base chat functionality and components
    - `rag_chat/` - RAG-specific chat implementation
    - `ai_expert/` - AI expert functionality
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

- **AI Expert** (`reflex/ai_expert/`)
  - `ai_expert_component.py` - AI expert interface
  - `ai_expert_state.py` - AI expert state management
  - `ai_expert_config_component.py` - AI expert configuration

### Routes
- `/` - Main chat page and entry point of the Reflex app
- `/history` - History page to view and browse past conversations
- `/ai-expert/:resourceId` - Chat with AI expert using specific document resources
- `/resource` - Resource management and knowledge base synchronization
- `/config` - Application configuration page
