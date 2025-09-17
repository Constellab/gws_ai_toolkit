
import json
import os
from typing import List, Optional, cast

import reflex as rx
from gws_core import BaseModelDTO, Table, TableUnfolderHelper
from openai import OpenAI
from pandas import DataFrame
from pydantic import BaseModel, Field

from gws_ai_toolkit.stats.ai_table_relation_stats import AiTableRelationStats
from gws_ai_toolkit.stats.ai_table_stats_base import AiTableStatsBase
from gws_ai_toolkit.stats.ai_table_stats_class import AiTableStats
from gws_ai_toolkit.stats.ai_table_stats_type import AiTableStatsResults

from ..ai_table_data_state import AiTableDataState


class AiTableStatsRunConfig(BaseModelDTO):
    ai_prompt: str
    columns: List[str]
    str_columns: str  # Comma-separated string of columns for display
    group_input: Optional[str]
    columns_are_paired: bool
    relation: bool  # True if relation/correlation analysis is needed
    reference_column: Optional[str]  # Optional reference column for relation analysis


class AiTableFunctionTool(BaseModel):
    selected_columns: List[str] = Field(
        description="List of column names to analyze (exact names from available columns)"
    )
    group_column: Optional[str] = Field(
        description="Optional column name to group by (exact name from available columns). Use null if no grouping needed."
    )
    columns_are_paired: bool = Field(
        description="True if the selected columns represent paired data that should be analyzed together, False if they are independent variables"
    )
    relation: bool = Field(
        description="True if the user wants correlation/relationship analysis (Pearson and Spearman tests) between 2 or more variables, False for standard statistical tests"
    )
    reference_column: Optional[str] = Field(
        description="Optional reference column for relation analysis. When specified with 3+ columns, only correlations between this reference column and all other columns are computed. Use null for all pairwise correlations."
    )

    class Config:
        extra = "forbid"  # Prevent additional properties


class AiTableStatsState(rx.State):
    """State for the AI Table stats component."""

    is_processing: bool = False
    _current_stats_analyzer: Optional[AiTableStatsBase] = None

    last_run_config: Optional[AiTableStatsRunConfig] = None
    ai_summary_response: Optional[str] = None

    @rx.event(background=True)  # type: ignore
    async def process_ai_prompt(self, form_data: dict):
        if self.is_processing:
            return rx.toast.error("Analysis already in progress. Please wait.")

        current_df: DataFrame | None
        async with self:
            self.clear_test_results()

            prompt = form_data.get("ai_prompt", "").strip()
            if not prompt:
                return rx.toast.error("Please enter a prompt describing your analysis.")

                # Get current dataframe to extract column names
            ai_table_state = await self.get_state(AiTableDataState)
            current_df = ai_table_state.get_current_dataframe

            if current_df is None or current_df.empty:
                return rx.toast.error("No dataframe available. Please load a file first.")

            self.is_processing = True

        try:
            # Convert prompt to analysis parameters using OpenAI
            last_run_config = await self._convert_prompt_to_analysis_params(
                prompt=prompt,
                current_df=current_df
            )

            if not last_run_config.columns:
                return rx.toast.error(
                    "Could not extract valid column names from the prompt. "
                    "Please check your prompt and ensure you reference existing column names.")

            async with self:
                self.last_run_config = last_run_config

            # Call the validation and analysis function
            toast = await self.validate_and_run_analysis(
                current_df=current_df,
                columns=last_run_config.columns,
                group_input=last_run_config.group_input,
                columns_are_paired=last_run_config.columns_are_paired,
                relation=last_run_config.relation,
                reference_column=last_run_config.reference_column
            )

            if toast:
                return toast

            # Generate AI summary response after analysis
            await self._generate_ai_summary_response()
        finally:
            async with self:
                self.is_processing = False

    async def _convert_prompt_to_analysis_params(self,
                                                 prompt: str,
                                                 current_df: DataFrame) -> AiTableStatsRunConfig:
        # Create OpenAI client
        client = self._get_openai_client()

        # Define the function schema for OpenAI
        tools = [
            {
                "type": "function",
                "function": {
                    "strict": True,
                    "name": "analyze_columns",
                    "description": "Extract column analysis parameters from user prompt",
                    "parameters": AiTableFunctionTool.model_json_schema()
                }
            }
        ]

        available_columns = list(current_df.columns)

        # Create column information with types
        column_info = []
        for col in available_columns:
            col_type = str(current_df[col].dtype)
            column_info.append(f"'{col}' ({col_type})")

        columns_with_types = ', '.join(column_info)

        # Create the system prompt with available columns and types
        system_prompt = f"""You are an expert data analyst. The user has a dataset with these columns: {columns_with_types}.

Based on their request, extract:
1. selected_columns: The exact column names they want to analyze (must match exactly from the available columns)
2. group_column: Optional column to group by (exact name, or null if no grouping)
3. columns_are_paired: Whether columns represent paired data (like before/after measurements) or independent variables
4. relation: Whether the user wants correlation/relationship analysis (Pearson and Spearman tests)
5. reference_column: Optional reference column for relation analysis (only used when relation=true and 3+ columns selected)

Important rules:
- Only use exact column names from the available list
- If a column is used as group_column, it cannot be in selected_columns
- Paired columns are used for related measurements (before/after, treatment/control, etc.)
- Independent columns are separate variables to compare

Relation analysis (correlation) detection:
- Set relation=true if the user asks about correlation, association, relationship, or connection between 2 or more variables
- Keywords that indicate relation analysis: "correlation", "relationship", "association", "connection", "related to", "depends on", "correlated with"
- Relation analysis requires 2 or more columns and no grouping
- Examples: "correlation between height and weight", "relationship between price and sales", "are age and income related?"

Reference column for relation analysis (only when relation=true):
- Use reference_column when the user wants to focus correlation analysis on one specific variable against all others
- Set reference_column=null for all pairwise correlations (default behavior)
- Examples with reference column: "how does price correlate with all other variables?", "show correlations of age against height, weight, and income"
- Examples without reference: "show all correlations between height, weight, age, and income", "correlation matrix of all variables"
- The reference_column must be one of the selected_columns

Available columns: {columns_with_types}"""

        # Create the input for OpenAI
        input_list = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        # Call OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=input_list,
            tools=tools,
            # force the model to use the function
            tool_choice={"type": "function", "function": {"name": "analyze_columns"}}
        )

        # Extract function call result
        if response.choices[0].message.tool_calls:
            tool_call = response.choices[0].message.tool_calls[0]
            if tool_call.function.name == "analyze_columns":
                function_args = json.loads(tool_call.function.arguments)

                selected_columns = function_args.get("selected_columns", [])

                return AiTableStatsRunConfig(
                    ai_prompt=prompt,
                    columns=selected_columns,
                    str_columns=", ".join(selected_columns),
                    group_input=function_args.get("group_column"),
                    columns_are_paired=function_args.get("columns_are_paired", False),
                    relation=function_args.get("relation", False),
                    reference_column=function_args.get("reference_column"),
                )

        return AiTableStatsRunConfig(
            ai_prompt=prompt,
            columns=[],
            str_columns="",
            group_input=None,
            columns_are_paired=False,
            relation=False,
            reference_column=None,
        )

    async def validate_and_run_analysis(
            self,
            current_df: DataFrame,
            columns: List[str],
            group_input: Optional[str],
            columns_are_paired: bool,
            relation: bool,
            reference_column: Optional[str] = None):

        available_columns = list(current_df.columns)

        # Basic validation - check for existence in dataframe
        missing_columns = []
        for col in columns:
            if col not in available_columns:
                missing_columns.append(col)

        # Show validation results for main columns
        if missing_columns:
            return rx.toast.error(
                f"Columns not found in dataframe: '{', '.join(missing_columns)}'. Available columns: '{', '.join(available_columns)}'")

        group_column: Optional[str] = None
        if group_input:
            # Handle group column (optional)
            group_column = group_input.strip()
            columns_are_paired = False  # Force independent if grouping

            if group_column in columns:
                # remove the group column from selected columns if present
                columns.remove(group_column)

            # Validate group column if provided
            if group_column not in available_columns:
                return rx.toast.error(
                    f"Group column '{group_column}' not found in dataframe. Available columns: '{', '.join(available_columns)}'")

            # If group column is provided, only allow 1 selected column
            if len(columns) > 1:
                return rx.toast.error(
                    f"When a group column is provided, only 1 column can be selected. You selected {len(columns)} columns: {', '.join(columns)}")

        # Check that all selected columns have the same number of non-null rows
        # row_counts = {}
        # for col in valid_columns:
        #     col_data = current_df[col]
        #     non_null_count = col_data.notna().sum()
        #     row_counts[col] = non_null_count

        # # Check if all columns have the same number of rows
        # unique_row_counts = set(row_counts.values())
        # if len(unique_row_counts) > 1:
        #     count_details = ', '.join([f"{col}: {count} rows" for col, count in row_counts.items()])
        #     return rx.toast.error(f"Selected columns have different numbers of non-null rows: {count_details}")

        # Filter and unfold the dataframe if group column is provided
        processed_df = self._get_filtered_and_unfolded_dataframe(
            selected_columns=columns,
            group_column=group_column,
            original_df=current_df
        )

        # Check if relation analysis is requested
        if relation:

            # Validate reference column for relation analysis if provided
            if reference_column:
                reference_column = self._get_and_check_reference_column(reference_column)

            # Create relation analyzer with optional reference column
            relation_analyzer = AiTableRelationStats(dataframe=processed_df, reference_column=reference_column)

            # Run correlation analysis
            relation_analyzer.run_correlation_analysis()

            # Store relation analyzer
            async with self:
                self._current_stats_analyzer = relation_analyzer

        # Generate AI summary response after analysis
        else:

            stats_analyzer = AiTableStats(
                dataframe=processed_df,
                columns_are_independent=not columns_are_paired,
            )

            # Run the statistical analysis decision tree
            stats_analyzer.run_statistical_analysis()

            # Store test history and current stats analyzer
            async with self:
                self._current_stats_analyzer = stats_analyzer

    async def _generate_ai_summary_response(self):
        """Generate a clear AI response combining the original prompt with statistical analysis results."""
        if not self._current_stats_analyzer or not self.last_run_config:
            return

        # Get the AI text summary from test history
        test_history = self._current_stats_analyzer.get_tests_history()
        ai_text_summary = test_history.get_ai_text_summary()

        if not ai_text_summary.strip():
            return

        # Get OpenAI client
        client = self._get_openai_client()

        # Prepare the prompt for OpenAI
        original_prompt = self.last_run_config.ai_prompt

        system_prompt = """You are an expert data analyst. You will receive:
1. The user's original analysis request/prompt
2. Statistical analysis results from tests that were run

Your task is to provide a clear, concise, and actionable response to the user's original question based on the statistical results.

Guidelines:
- Answer the user's specific question directly
- Use plain language, avoid unnecessary technical jargon
- Highlight key findings and their practical significance
- If the results show significance, explain what this means in context
- If results are not significant, explain what this suggests
- Keep the response focused and relevant to the original question"""

        user_message = f"""Original user question: "{original_prompt}"

Statistical analysis results:
{ai_text_summary}

Please provide a clear, direct answer to the user's original question based on these statistical results."""

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3
            )

            # Store the AI response (you might want to add a state variable for this)
            ai_response = response.choices[0].message.content
            if ai_response:
                async with self:
                    self.ai_summary_response = ai_response.strip()

        except Exception as e:
            # Handle API errors gracefully
            async with self:
                self.ai_summary_response = f"Error generating summary: {str(e)}"

    def _get_filtered_and_unfolded_dataframe(self, selected_columns: list,
                                             group_column: Optional[str],
                                             original_df: DataFrame):
        """
        Filter the dataframe to selected columns + group column, then unfold by group column.

        :param selected_columns: List of selected column names
        :param group_column: Name of the group column to unfold by
        :param original_df: Original dataframe
        :return: Filtered and unfolded DataFrame
        """
        # If no group column, return the filtered dataframe as-is
        if not group_column:
            return original_df[selected_columns]

        # Create columns to include (selected columns + group column)
        columns_to_include = selected_columns.copy()
        if group_column and group_column not in columns_to_include:
            columns_to_include.append(group_column)

        # Filter the dataframe to only include the selected columns and group column
        filtered_df = original_df[columns_to_include]

        # Create a Table from the filtered dataframe
        table = Table(filtered_df)

        # Create unfolder helper and unfold by the group column
        unfolder_helper = TableUnfolderHelper()
        unfolded_table = unfolder_helper.unfold_by_columns(table, [group_column])

        # Return the unfolded dataframe
        return unfolded_table.get_data()

    @rx.var
    def test_history(self) -> List[AiTableStatsResults]:
        """Get the test history."""
        if self._current_stats_analyzer:
            return self._current_stats_analyzer.get_tests_history().get_results()
        return []

    @rx.var
    def last_test_result(self) -> Optional[AiTableStatsResults]:
        """Get the last test result."""
        # Get the last test result if available
        if self.test_history:
            return self.test_history[-1]
        else:
            return None

    @rx.var
    def suggested_additional_test(self) -> Optional[str]:
        """Get suggested additional test if any."""
        if self._current_stats_analyzer:
            return self._current_stats_analyzer.suggested_additional_tests()
        return None

    @rx.var
    def has_suggested_additional_test(self) -> bool:
        """Check if there's a suggested additional test."""
        return self.suggested_additional_test is not None

    @rx.event
    def clear_test_results(self):
        """Clear test history and last test results."""
        self._current_stats_analyzer = None
        self.last_run_config = None
        self.ai_summary_response = None

    @rx.event(background=True)  # type: ignore
    async def run_additional_test_with_reference_column(self, form_data: dict):
        """Run additional test with reference column from form."""
        if self.is_processing:
            return rx.toast.error("Analysis already in progress. Please wait.")

        if not self._current_stats_analyzer or not self.last_run_config:
            return rx.toast.error("No statistical analysis available. Please run an analysis first.")

        stats_analyzer = cast(AiTableStats, self._current_stats_analyzer)
        if not isinstance(stats_analyzer, AiTableStats):
            return rx.toast.error(
                "Additional tests can only be run for standard statistical analyses, not relation analyses.")

        # Get reference column/group from form
        reference_input: str = form_data.get("reference_column", "")

        # Compute actual reference column name based on group_input
        reference_column: str | None = self._get_and_check_reference_column(reference_input)

        async with self:
            self.is_processing = True

        try:
            # Run pairwise test with reference column
            stats_analyzer.run_student_independent_pairwise(reference_column)

        finally:
            async with self:
                self.is_processing = False
                self._current_stats_analyzer = self._current_stats_analyzer  # Trigger state update

    def _get_and_check_reference_column(self, reference_input: str) -> Optional[str]:
        # Compute actual reference column name based on group_input

        if not reference_input or not self.last_run_config or not self._current_stats_analyzer:
            return None

        reference_input = reference_input.strip()

        if self.last_run_config.group_input:
            # For grouped data: format as 'COLUMN_GROUP'
            first_column = self.last_run_config.columns[0] if self.last_run_config.columns else ""
            reference_column = f"{first_column}_{reference_input}"

            # Use AiTableStats methods to validate column existence
            if not self._current_stats_analyzer.has_column(reference_column):
                raise ValueError(
                    f"Reference group '{reference_input}' not found in the column '{self.last_run_config.group_input}'.")

            return reference_column

        else:
            # For non-grouped data: use input as column name directly
            # Use AiTableStats methods to validate column existence
            if not self._current_stats_analyzer.has_column(reference_input):
                raise ValueError(
                    f"Reference column '{reference_input}' not found in dataframe or is not a selected column.")

            return reference_input

    def _get_openai_client(self) -> OpenAI:
        """Get OpenAI client with API key"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key is not set")
        return OpenAI(api_key=api_key)
