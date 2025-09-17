# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository. All path are relative to location of this file.

## Project Overview

GWS AI Toolkit is a Constellab brick (library) developed by Gencovery that provides AI-driven tools for data analysis and visualization in the life sciences. It depends on the `gws_core` brick (version 0.16.1) and includes RAG (Retrieval Augmented Generation) implementations for Dify and RagFlow platforms, plus a standalone Reflex-based RAG application.

## Architecture

### Directory Structure
- `src/gws_ai_toolkit/` - Main RAG implementations
  - `rag/` - RAG services and integrations
  - `stats/` - Tools to perform statistical analysis and generate visualizations
  - `core/` - Core utilities and helpers
    - `agents/` - Base and specialized agent implementations
  - `ai_table_standalone_app/` - Standalone Reflex-based AI Table application
- `tests/test_gws_ai_toolkit/` - Test files


## Applications
- RAG app directory: `src/gws_ai_toolkit/rag/rag_app/_rag_app/`
  - CONFIG_FILE_PATH: `src/gws_ai_toolkit/rag/rag_app/_rag_app/dev_config.json`
- Ai Table app directory: `src/gws_ai_toolkit/ai_table_standalone_app/_ai_table_standalone_app/`
  - CONFIG_FILE_PATH: `src/gws_ai_toolkit/ai_table_standalone_app/_ai_table_standalone_app/dev_config.json`

### Dependencies
- `gws_core` (v0.16.1) - Core Constellab functionality including BaseModelDTO, credentials, external API services
- `reflex` (v0.8.8) - Web framework for the RAG application

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
- set the imports on top of the file

### Start RAG app
- Run the RAG app locally: `gws reflex run-dev [CONFIG_FILE_PATH]` 
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