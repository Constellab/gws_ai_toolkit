from typing import Optional

from gws_core import Logger
from pandas import DataFrame, api

from .ai_table_stats_base import AiTableStatsBase
from .ai_table_stats_tests import AiTableStatsTests
from .ai_table_stats_tests_pairwise import AiTableStatsTestsPairWise


class AiTableRelationStats(AiTableStatsBase):
    """
    Statistical analysis class specialized for correlation and relationship analysis.

    RELATION ANALYSIS DECISION TREE:

    1. DATA TYPE VALIDATION:
       - Requires at least 2 quantitative (numeric) columns
       - If less than 2 columns or not quantitative → Error

    2. CORRELATION ANALYSIS:
       For 2 columns:
       - Pearson correlation test: Tests for linear correlation between two variables
       - Spearman correlation test: Tests for monotonic correlation between two variables
       - Both tests are always performed for comprehensive relationship analysis

       For more than 2 columns:
       - Pairwise Pearson correlation test: Tests all pairs or reference vs all others
       - Pairwise Spearman correlation test: Tests all pairs or reference vs all others
       - If reference_column is provided, only tests reference vs all other columns

    3. INTERPRETATION:
       - Pearson: Measures strength of linear relationship (-1 to +1)
       - Spearman: Measures strength of monotonic relationship (-1 to +1)
       - Both provide p-values for statistical significance testing

    This class is designed to be used as a separate analysis branch from the main
    statistical tests in AiTableStats, focusing specifically on relationships
    between variables.
    """

    _reference_column: Optional[str]

    def __init__(self, dataframe: DataFrame, reference_column: Optional[str] = None):
        super().__init__(dataframe)

        self._reference_column = reference_column

    def validate_data(self) -> None:
        """Validate that the data is suitable for relation analysis."""
        num_columns = len(self._dataframe.columns)

        if num_columns < 2:
            raise ValueError(f"Relation analysis requires at least 2 columns, got {num_columns}")

        # Check if columns are quantitative
        if not all(api.types.is_numeric_dtype(self._dataframe[col]) for col in self._dataframe.columns):
            raise ValueError("Relation analysis requires quantitative (numeric) columns")

        # Validate reference column if provided
        if self._reference_column and self._reference_column not in self._dataframe.columns:
            raise ValueError(
                f"Reference column '{self._reference_column}' not found in dataframe columns: {list(self._dataframe.columns)}")

    def run_correlation_analysis(self) -> None:
        """Run correlation analysis between columns."""
        # Validate data first
        self.validate_data()

        Logger.debug("Starting correlation analysis")
        num_columns = self.count_columns()

        if num_columns == 2:
            # Two-column case: Use traditional pairwise correlation
            Logger.debug("Running two-column correlation analysis")

            tests_ = AiTableStatsTests()

            # Get the two columns
            col1_data = self._dataframe.iloc[:, 0]
            col2_data = self._dataframe.iloc[:, 1]

            # Run Pearson correlation test
            Logger.debug("Running: Pearson correlation")
            pearson_result = tests_.pearson_correlation_test(col1_data, col2_data)
            self._record_test(pearson_result)
            Logger.debug(f"Pearson Result: {pearson_result}")

            # Run Spearman correlation test
            Logger.debug("Running: Spearman correlation")
            spearman_result = tests_.spearman_correlation_test(col1_data, col2_data)
            self._record_test(spearman_result)
            Logger.debug(f"Spearman Result: {spearman_result}")

        else:
            tests_ = AiTableStatsTestsPairWise()
            # Multi-column case: Use pairwise correlation tests
            Logger.debug(f"Running multi-column pairwise correlation analysis ({num_columns} columns)")
            if self._reference_column:
                Logger.debug(f"Using reference column: {self._reference_column}")
            else:
                Logger.debug("Performing all pairwise comparisons")

            # Run Pearson pairwise correlation test
            Logger.debug("Running: Pearson pairwise correlation")
            pearson_result = tests_.pearson_correlation_pairwise_test(
                self._dataframe, reference_column=self._reference_column
            )
            self._record_test(pearson_result)
            Logger.debug(f"Pearson Pairwise Result: {pearson_result}")

            # Run Spearman pairwise correlation test
            Logger.debug("Running: Spearman pairwise correlation")
            spearman_result = tests_.spearman_correlation_pairwise_test(
                self._dataframe, reference_column=self._reference_column
            )
            self._record_test(spearman_result)
            Logger.debug(f"Spearman Pairwise Result: {spearman_result}")
