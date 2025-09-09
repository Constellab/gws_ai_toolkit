
from dataclasses import dataclass
from typing import Callable, List

import reflex as rx

from ...chat_base.base_analysis_config import BaseAnalysisConfig


@dataclass
class AiTableChatConfigUI:
    """UI configuration class for AI Table interface customization.

    This dataclass defines UI-specific configuration options for the AI Table
    component, allowing customization of the interface elements and behavior.

    Attributes:
        header_buttons (Callable[[], List[rx.Component]] | None): Optional callable
            that returns a list of custom header buttons to display in the AI Table
            chat interface. If None, default header buttons are used.

    Example:
        def custom_buttons() -> List[rx.Component]:
            return [rx.button("Custom Action", on_click=custom_handler)]

        config = AiTableConfigUI(header_buttons=custom_buttons)
    """

    # Add custom button on top right of the header
    header_buttons: Callable[[], List[rx.Component]] | None = None


class AiTableChatConfig(BaseAnalysisConfig):
    """Configuration class for AI Table functionality.

    This class defines configurable parameters specific to the AI Table chat system
    for Excel/CSV analysis. It extends BaseAnalysisConfig to inherit common parameters
    while providing table-specific system prompts.

    The AI Table only supports full_file mode, where the Excel/CSV file is uploaded
    to the AI for complete document analysis with pandas/data processing capabilities.
    """

    system_prompt: str = """You are an AI data analyst specialized in analyzing and answering questions about the Excel/CSV file "[FILE]".

You have access to the full content of this tabular data file and can perform comprehensive data analysis using pandas and other data processing tools.

When analyzing the data:
- Use pandas to load, explore, and manipulate the data
- Provide statistical summaries, insights, and visualizations when relevant
- Answer specific questions about the data structure, patterns, and content
- Generate code examples for data manipulation when helpful
- Create charts and visualizations to illustrate findings
- If something is not present in the data, clearly state this
- Be thorough in your analysis and provide actionable insights
- You must return the resulting files for download from the API. Do not return the file path in your markdown response.

The user is asking questions specifically about this tabular data, so focus your responses on data analysis, statistics, trends, and insights derived from the file content."""
