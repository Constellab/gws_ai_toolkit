from typing import Optional

import pandas as pd
from scipy.stats import pearsonr, spearmanr
from statsmodels.stats.weightstats import ttest_ind

from .ai_table_stats_plots import AiTableStatsPlots
from .ai_table_stats_type import (AiTableStatsResults,
                                  CorrelationPairwiseDetails,
                                  StudentTTestPairwiseDetails)


class AiTableStatsTestsPairWise:
    """Class containing pairwise statistical tests for AI Table Stats analysis."""

    plots = AiTableStatsPlots()

    def _perform_pairwise_analysis(self, dataframe: pd.DataFrame, reference_column: Optional[str],
                                   comparison_function, test_name: str,
                                   details_class, diagonal_p_value: float = 0.0,
                                   diagonal_stat_value: float = 1.0) -> AiTableStatsResults:
        """
        Generic method for performing pairwise statistical comparisons.

        Args:
            dataframe: DataFrame containing the data
            reference_column: Optional reference column for comparisons
            comparison_function: Function that performs the statistical test (should return statistic, p_value)
            test_name: Name of the test for the result
            details_class: Class to use for details in result
            diagonal_p_value: Value to use for diagonal p-values (default 0.0)
            diagonal_stat_value: Value to use for diagonal statistics (default 1.0)
        """
        # Get all columns
        columns = dataframe.columns.tolist()

        if len(columns) < 2:
            raise ValueError("The table must contain at least two columns for pairwise comparisons.")

        if reference_column and reference_column not in columns:
            raise ValueError(f"Reference column '{reference_column}' not found in dataframe columns.")

        # Initialize matrices for p-values and statistics
        p_value_matrix = pd.DataFrame(index=columns, columns=columns, dtype=float)
        statistic_matrix = pd.DataFrame(index=columns, columns=columns, dtype=float)

        # Set diagonal values
        for col in columns:
            p_value_matrix.loc[col, col] = diagonal_p_value
            statistic_matrix.loc[col, col] = diagonal_stat_value

        # Perform pairwise comparisons
        valid_comparisons = 0
        significant_count = 0

        if reference_column:
            # Only compare reference column with all other columns
            for col in columns:
                if col != reference_column:
                    # Find common indices for proper pairing
                    common_indices = dataframe[[reference_column, col]].dropna().index
                    if len(common_indices) > 1:
                        col1_paired = dataframe.loc[common_indices, reference_column]
                        col2_paired = dataframe.loc[common_indices, col]

                        statistic, p_value = comparison_function(col1_paired, col2_paired)
                        p_value_matrix.loc[reference_column, col] = float(p_value)
                        statistic_matrix.loc[reference_column, col] = float(statistic)

                        # Also set the symmetric entry in the matrix
                        p_value_matrix.loc[col, reference_column] = float(p_value)
                        statistic_matrix.loc[col, reference_column] = float(statistic)

                        valid_comparisons += 1
                        if p_value < 0.05:
                            significant_count += 1
                    else:
                        p_value_matrix.loc[reference_column, col] = None
                        statistic_matrix.loc[reference_column, col] = None
                        p_value_matrix.loc[col, reference_column] = None
                        statistic_matrix.loc[col, reference_column] = None

            # Set all non-reference comparisons to None
            for i, col1 in enumerate(columns):
                for j, col2 in enumerate(columns):
                    if col1 != reference_column and col2 != reference_column and i != j:
                        p_value_matrix.loc[col1, col2] = None
                        statistic_matrix.loc[col1, col2] = None
        else:
            # Original behavior: all pairwise combinations
            for i, col1 in enumerate(columns):
                for j, col2 in enumerate(columns):
                    if i != j:  # Skip diagonal
                        # Find common indices for proper pairing
                        common_indices = dataframe[[col1, col2]].dropna().index
                        if len(common_indices) > 1:
                            col1_paired = dataframe.loc[common_indices, col1]
                            col2_paired = dataframe.loc[common_indices, col2]

                            statistic, p_value = comparison_function(col1_paired, col2_paired)
                            p_value_matrix.loc[col1, col2] = float(p_value)
                            statistic_matrix.loc[col1, col2] = float(statistic)

                            # Only count each pair once for statistics
                            if i < j:
                                valid_comparisons += 1
                                if p_value < 0.05:
                                    significant_count += 1
                        else:
                            p_value_matrix.loc[col1, col2] = None
                            statistic_matrix.loc[col1, col2] = None

        if valid_comparisons == 0:
            raise ValueError("No valid pairs with data found for statistical analysis.")

        # Create combined matrix with p-values as the main result
        if reference_column:
            # When reference column is provided, return only the reference column data
            comparison_matrix = p_value_matrix[[reference_column]]
        else:
            comparison_matrix = p_value_matrix

        # Generate appropriate result text based on test type
        if "correlation" in test_name.lower():
            if significant_count > 0:
                result_text = f"Significant correlations found in {significant_count} of {valid_comparisons} pairwise comparisons."
            else:
                result_text = "No significant pairwise correlations found."
        else:
            if significant_count > 0:
                result_text = f"Significant differences found in {significant_count} of {valid_comparisons} pairwise comparisons."
            else:
                result_text = "No significant pairwise differences found."

        return AiTableStatsResults(
            test_name=test_name,
            result_text=result_text,
            result_figure=None,
            statistic=None,
            p_value=None,
            details=details_class(
                pairwise_comparisons_matrix=comparison_matrix,
                significant_comparisons=significant_count,
                total_comparisons=valid_comparisons
            )
        )

    def student_independent_pairwise_test(
            self, dataframe: pd.DataFrame, reference_column: Optional[str] = None) -> AiTableStatsResults:
        """Student's t-test for independent pairwise comparisons (post-hoc after ANOVA).

        Args:
            dataframe: DataFrame containing the data
            reference_column: Optional reference column. If provided, comparisons are only made
                            between this column and all other columns. If None, all pairwise
                            combinations are tested.
        """
        # Use the helper method with t-test wrapper
        return self._perform_pairwise_analysis(
            dataframe=dataframe,
            reference_column=reference_column,
            comparison_function=self._ttest_wrapper,
            test_name='Student t-test (independent paired wise)',
            details_class=StudentTTestPairwiseDetails,
            diagonal_p_value=1.0,
            diagonal_stat_value=1.0  # t-statistic for comparison with self is 0
        )

    def _ttest_wrapper(self, group1: pd.Series, group2: pd.Series) -> tuple[float, float]:
        """Wrapper for t-test to match the interface expected by _perform_pairwise_analysis."""
        statistic, p_value, _ = ttest_ind(group1, group2, usevar='pooled')
        return float(statistic), float(p_value)

    def pearson_correlation_pairwise_test(
            self, dataframe: pd.DataFrame, reference_column: Optional[str] = None) -> AiTableStatsResults:
        """Pearson correlation test for pairwise comparisons.

        Args:
            dataframe: DataFrame containing the data
            reference_column: Optional reference column. If provided, correlations are only computed
                            between this column and all other columns. If None, all pairwise
                            combinations are tested.
        """
        # Use the helper method with Pearson correlation
        return self._perform_pairwise_analysis(
            dataframe=dataframe,
            reference_column=reference_column,
            comparison_function=pearsonr,
            test_name='Pearson correlation',
            details_class=CorrelationPairwiseDetails,
            diagonal_p_value=1.0,
            diagonal_stat_value=1.0
        )

    def spearman_correlation_pairwise_test(
            self,
            dataframe: pd.DataFrame,
            reference_column: Optional[str] = None) -> AiTableStatsResults:
        """Spearman rank correlation test for pairwise comparisons.

        Args:
            dataframe: DataFrame containing the data
            reference_column: Optional reference column. If provided, correlations are only computed
                            between this column and all other columns. If None, all pairwise
                            combinations are tested.
        """
        # Use the helper method with Spearman correlation
        return self._perform_pairwise_analysis(
            dataframe=dataframe,
            reference_column=reference_column,
            comparison_function=spearmanr,
            test_name='Spearman correlation',
            details_class=CorrelationPairwiseDetails,
            diagonal_p_value=1.0,
            diagonal_stat_value=1.0
        )
