"""AI Table module for Excel/CSV data analysis chat functionality.

This module provides specialized chat components and state management for analyzing
Excel and CSV files using AI-powered data analysis capabilities. It includes:

Components:
    - AiTableState: Core state management for Excel/CSV file analysis
    - AiTableConfigState: Configuration management for AI Table settings  
    - AiTableConfig: Configuration data model
    - ai_table_component: Main chat interface component
    - ai_table_config_component: Configuration UI component

Key Features:
    - Full file upload to OpenAI with code interpreter access
    - Pandas-based data analysis and statistical computations
    - Data visualization generation
    - Excel (.xlsx, .xls) and CSV file support
    - Conversation history persistence
    - Configurable AI models and parameters

Usage:
    from .ai_table_state import AiTableState
    from .ai_table_component import ai_table_component
    from .ai_table_config_component import ai_table_config_component
"""

from .ai_table_component import ai_table_component
from .ai_table_config import AiTableConfig, AiTableConfigUI  
from .ai_table_config_component import ai_table_config_component
from .ai_table_config_state import AiTableConfigState
from .ai_table_state import AiTableState

__all__ = [
    "AiTableState",
    "AiTableConfig", 
    "AiTableConfigUI",
    "AiTableConfigState",
    "ai_table_component",
    "ai_table_config_component",
]