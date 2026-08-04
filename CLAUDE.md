# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository. All path are relative to location of this file.

## Project Overview

GWS AI Toolkit is a Constellab brick (library) developed by Gencovery that provides AI-driven tools for data analysis and visualization in the life sciences. It depends on the `gws_core` brick (see `settings.json` for the current version) and includes RAG (Retrieval Augmented Generation) implementations for Dify and RagFlow platforms, plus a standalone Reflex-based RAG application.

## Architecture

### Directory Structure
- `src/gws_ai_toolkit/` - Main RAG implementations
  - `apps/` - Reflex applications and their generator tasks (`rag_app/`, `ai_table_standalone_app/`, `full_app/`)
  - `rag/` - RAG services and integrations (Dify, RagFlow) under `rag/common/`, `rag/dify/`, `rag/ragflow/`
  - `models/` - Peewee persistence models (chat conversations/messages/sources, users, knowledge bases). Tables auto-create at brick load, so every model must be imported from `src/gws_ai_toolkit/__init__.py` — a model nothing imports is a table that is never created.
  - `services/` - Service layer
  - `tasks/` - Task implementations
  - `stats/` - Tools to perform statistical analysis and generate visualizations
  - `core/` - Core utilities and helpers
    - `agents/` - Base and specialized agent implementations
  - `_app/` - Re-export facades for app components (Reflex components only, not tasks)
- `tests/test_gws_ai_toolkit/` - Test files
- `docs/todo/` / `docs/done/` - Plan documents (pending / implemented)


## Applications
- RAG app directory: `src/gws_ai_toolkit/apps/rag_app/_rag_app/`
  - CONFIG_FILE_PATH: `src/gws_ai_toolkit/apps/rag_app/_rag_app/dev_config.json`
- Ai Table app directory: `src/gws_ai_toolkit/apps/ai_table_standalone_app/_ai_table_standalone_app/`
  - CONFIG_FILE_PATH: `src/gws_ai_toolkit/apps/ai_table_standalone_app/_ai_table_standalone_app/dev_config.json`
- Full app directory: `src/gws_ai_toolkit/apps/full_app/_full_app/`
  - CONFIG_FILE_PATH: `src/gws_ai_toolkit/apps/full_app/_full_app/dev_config.json`

### Dependencies
- `gws_core` - Core Constellab functionality including BaseModelDTO, credentials, external API services; also provides `reflex` (the web framework used by the apps). Current pinned version: see `settings.json`
- Brick-specific pip packages (see `settings.json`): `ragflow-sdk`, `reflex-resizable-panels`, `scikit-posthocs`

### Development best practises
- Follow a modular architecture for components and pages
- Split the application into components. A component is defined by a folder containing the component and state file inside. Ex:
  - `chat/`
    - `chat/chat_component.py` (UI component)
    - `chat/chat_state.py` (state management)
- Use state management effectively to handle application state
- Keep UI components reusable and maintainable
- All the import from the rag_app that reference another file in the rag_app MUST be relative imports. Ex: `from .reflex import ai_expert_config_component` instead of `from gws_ai_toolkit.apps.rag_app._rag_app.rag_app.reflex import ai_expert_config_component`
- Define the attributes, parameters and return types of functions, methods and classes using type hints
- for the `rx.button` :
  - For primary and secondary button leave color_scheme to default.
  - For warning buttons use `color_scheme="red"`


- set the imports on top of the file

### Start RAG app
- Run the RAG app locally: `gws reflex run [CONFIG_FILE_PATH]` 
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

## Testing
- Tests are located in `tests/test_gws_ai_toolkit/`
- Use `gws server test [FILENAME]` to run tests

## Agent skills

### Issue tracker

Issues and PRDs live as GitHub issues in `Constellab/gws_ai_toolkit`, managed with the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles are used verbatim as label strings. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` plus `docs/adr/` at the repo root. See `docs/agents/domain.md`.