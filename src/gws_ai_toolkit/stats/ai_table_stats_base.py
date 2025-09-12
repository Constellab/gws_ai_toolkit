

from typing import Optional

from pandas import DataFrame, api

from .ai_table_stats_type import (AiTableStatsResultList, AiTableStatsResults,
                                  AiTableStatsTestName)


class AiTableStatsBase:

    _dataframe: DataFrame
    _tests_history: AiTableStatsResultList

    def __init__(self, dataframe: DataFrame):
        self._dataframe = dataframe.dropna()
        self._tests_history = AiTableStatsResultList()

    def suggested_additional_tests(self) -> Optional[str]:
        """Suggest additional tests based on current data and previous tests.

        Returns:
            Optional[str]: Suggestion text or None if no suggestions
        """
        return None

    def has_column(self, column_name: str) -> bool:
        return column_name in self._dataframe.columns

    def count_columns(self) -> int:
        """Get the number of columns in the dataframe."""
        return len(self._dataframe.columns)

    def columns_are_quantitative(self) -> bool:
        """Check if all columns are quantitative (numeric)"""
        return all(api.types.is_numeric_dtype(self._dataframe[col]) for col in self._dataframe.columns)

    def get_tests_history(self) -> AiTableStatsResultList:
        """Get the history of all statistical tests performed."""
        return self._tests_history

    def _record_test(self, result: AiTableStatsResults) -> None:
        """Record a test result in the history."""
        self._tests_history.add_result(result)

    def history_contains(self, test_name: AiTableStatsTestName) -> bool:
        """
        Check if a specific test has been performed.

        Args:
            test_name: Name of the test to check
        Returns:
            True if the test has been performed, False otherwise
        """
        return self._tests_history.contains_test(test_name)
