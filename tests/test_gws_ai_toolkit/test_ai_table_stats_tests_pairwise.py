from unittest import TestCase

import numpy as np
import pandas as pd
from gws_ai_toolkit.stats.ai_table_stats_tests import AiTableStatsTests
from gws_ai_toolkit.stats.ai_table_stats_tests_pairwise import AiTableStatsTestsPairWise
from gws_ai_toolkit.stats.ai_table_stats_type import (
    AiTableStatsResults,
    CorrelationPairwiseDetails,
    StudentTTestPairwiseDetails,
)


# test_ai_table_stats_tests_pairwise.py
class TestAiTableStatsTestsPairWise(TestCase):
    """Unit tests for AiTableStatsTestsPairWise class."""

    def setUp(self):
        """Set up test fixtures."""
        self.pairwise_tests = AiTableStatsTestsPairWise()

        # Create test data with multiple columns
        np.random.seed(42)  # For reproducible tests
        self.test_df = pd.DataFrame(
            {
                "Group_A": np.random.normal(0, 1, 50),
                "Group_B": np.random.normal(1, 1, 50),
                "Group_C": np.random.normal(2, 1, 50),
                "Group_D": np.random.normal(0.5, 1.5, 50),
            }
        )

        # Create correlated data for correlation tests
        x = np.random.normal(0, 1, 40)
        self.correlation_df = pd.DataFrame(
            {
                "Variable_1": x,
                "Variable_2": 0.7 * x + np.random.normal(0, 0.5, 40),  # Strong correlation
                "Variable_3": 0.3 * x + np.random.normal(0, 1, 40),  # Weak correlation
                "Variable_4": np.random.normal(0, 1, 40),  # No correlation
            }
        )

        # Create DataFrame with missing values
        self.df_with_missing = pd.DataFrame(
            {
                "Col_A": [1, 2, 3, np.nan, 5],
                "Col_B": [2, 3, np.nan, 5, 6],
                "Col_C": [3, 4, 5, 6, np.nan],
            }
        )

        # Small DataFrame for edge case testing
        self.small_df = pd.DataFrame({"X": [1, 2, 3], "Y": [2, 4, 6]})

    def test_student_independent_pairwise_test_all_pairs(self):
        """Test Student's t-test for all pairwise combinations."""
        result = self.pairwise_tests.student_independent_pairwise_test(self.test_df)

        self.assertIsInstance(result, AiTableStatsResults)
        self.assertEqual(result.test_name, "Student t-test (independent paired wise)")
        self.assertIsInstance(result.details, StudentTTestPairwiseDetails)
        self.assertIsInstance(result.details.pairwise_comparisons_matrix, pd.DataFrame)
        self.assertIsInstance(result.details.significant_comparisons, int)
        self.assertIsInstance(result.details.total_comparisons, int)
        self.assertIn("pairwise", result.result_text.lower())

        # Check matrix dimensions
        matrix = result.details.pairwise_comparisons_matrix
        expected_cols = len(self.test_df.columns)
        self.assertEqual(matrix.shape, (expected_cols, expected_cols))

        # Check diagonal values are 1.0 (p-value for comparing column with itself)
        for col in matrix.columns:
            self.assertEqual(matrix.loc[col, col], 1.0)

        # Check that correction is running without error with the generated matrix
        simple_test = AiTableStatsTests()
        simple_test.bonferroni_test(matrix)
        simple_test.tukey_hsd_test(matrix)

    def test_student_independent_pairwise_test_with_reference(self):
        """Test Student's t-test with reference column."""
        reference_col = "Group_A"
        result = self.pairwise_tests.student_independent_pairwise_test(
            self.test_df, reference_column=reference_col
        )

        self.assertIsInstance(result, AiTableStatsResults)
        self.assertIsInstance(result.details, StudentTTestPairwiseDetails)

        # Check that only reference column comparisons are returned
        matrix = result.details.pairwise_comparisons_matrix
        self.assertEqual(matrix.shape[1], 1)  # Only one column (reference)
        self.assertEqual(matrix.columns[0], reference_col)

        # Check that comparisons exist for reference column vs others
        non_null_values = matrix[reference_col].notna().sum()
        self.assertEqual(non_null_values, len(self.test_df.columns))  # Including diagonal

    def test_pearson_correlation_pairwise_test_all_pairs(self):
        """Test Pearson correlation for all pairwise combinations."""
        result = self.pairwise_tests.pearson_correlation_pairwise_test(self.correlation_df)

        self.assertIsInstance(result, AiTableStatsResults)
        self.assertEqual(result.test_name, "Pearson correlation")
        self.assertIsInstance(result.details, CorrelationPairwiseDetails)
        self.assertIsInstance(result.details.pairwise_comparisons_matrix, pd.DataFrame)
        self.assertIn("correlation", result.result_text.lower())

        # Check matrix dimensions
        matrix = result.details.pairwise_comparisons_matrix
        expected_cols = len(self.correlation_df.columns)
        self.assertEqual(matrix.shape, (expected_cols, expected_cols))

        # Check diagonal values are 1.0 (p-value for perfect correlation with itself)
        for col in matrix.columns:
            self.assertEqual(matrix.loc[col, col], 1.0)

        # Check that dunnett test is running without error with the generated matrix
        simple_test = AiTableStatsTests()
        simple_test.benjamini_hochberg_test(matrix)
        simple_test.holm_test(matrix)

    def test_pearson_correlation_pairwise_test_with_reference(self):
        """Test Pearson correlation with reference column."""
        reference_col = "Variable_1"
        result = self.pairwise_tests.pearson_correlation_pairwise_test(
            self.correlation_df, reference_column=reference_col
        )

        self.assertIsInstance(result, AiTableStatsResults)
        self.assertIsInstance(result.details, CorrelationPairwiseDetails)

        # Check that only reference column comparisons are returned
        matrix = result.details.pairwise_comparisons_matrix
        self.assertEqual(matrix.shape[1], 1)  # Only one column (reference)
        self.assertEqual(matrix.columns[0], reference_col)

    def test_spearman_correlation_pairwise_test_all_pairs(self):
        """Test Spearman correlation for all pairwise combinations."""
        result = self.pairwise_tests.spearman_correlation_pairwise_test(self.correlation_df)

        self.assertIsInstance(result, AiTableStatsResults)
        self.assertEqual(result.test_name, "Spearman correlation")
        self.assertIsInstance(result.details, CorrelationPairwiseDetails)
        self.assertIsInstance(result.details.pairwise_comparisons_matrix, pd.DataFrame)
        self.assertIn("correlation", result.result_text.lower())

        # Check matrix dimensions
        matrix = result.details.pairwise_comparisons_matrix
        expected_cols = len(self.correlation_df.columns)
        self.assertEqual(matrix.shape, (expected_cols, expected_cols))

        # Check that dunnett test is running without error with the generated matrix
        simple_test = AiTableStatsTests()
        simple_test.benjamini_hochberg_test(matrix)
        simple_test.holm_test(matrix)

    def test_spearman_correlation_pairwise_test_with_reference(self):
        """Test Spearman correlation with reference column."""
        reference_col = "Variable_2"
        result = self.pairwise_tests.spearman_correlation_pairwise_test(
            self.correlation_df, reference_column=reference_col
        )

        self.assertIsInstance(result, AiTableStatsResults)
        self.assertIsInstance(result.details, CorrelationPairwiseDetails)

        # Check that only reference column comparisons are returned
        matrix = result.details.pairwise_comparisons_matrix
        self.assertEqual(matrix.shape[1], 1)  # Only one column (reference)
        self.assertEqual(matrix.columns[0], reference_col)

    def test_handling_missing_values(self):
        """Test that missing values are properly handled."""
        result = self.pairwise_tests.student_independent_pairwise_test(self.df_with_missing)

        self.assertIsInstance(result, AiTableStatsResults)
        self.assertIsInstance(result.details, StudentTTestPairwiseDetails)

        # Should still produce results despite missing values
        self.assertGreater(result.details.total_comparisons, 0)

    def test_significant_comparisons_detection(self):
        """Test detection of significant comparisons."""
        # Create data with clear differences
        significant_df = pd.DataFrame(
            {
                "Low_Group": np.full(30, 0),  # Mean = 0
                "High_Group": np.full(30, 10),  # Mean = 10, should be significantly different
                "Mid_Group": np.full(30, 5),  # Mean = 5
            }
        )

        result = self.pairwise_tests.student_independent_pairwise_test(significant_df)

        # Should detect significant differences
        self.assertGreater(result.details.significant_comparisons, 0)
        self.assertIn("significant", result.result_text.lower())

    def test_no_significant_comparisons(self):
        """Test when no significant comparisons are found."""
        # Create data with very similar means
        similar_df = pd.DataFrame(
            {
                "Group1": np.random.normal(5.0, 0.01, 20),
                "Group2": np.random.normal(5.01, 0.01, 20),
                "Group3": np.random.normal(5.02, 0.01, 20),
            }
        )

        result = self.pairwise_tests.student_independent_pairwise_test(similar_df)

        # May or may not find significant differences depending on random data
        # But should handle the case gracefully
        self.assertIsInstance(result.details.significant_comparisons, int)
        self.assertGreaterEqual(result.details.significant_comparisons, 0)

    def test_strong_correlation_detection(self):
        """Test detection of strong correlations."""
        # Create strongly correlated data
        strong_corr_df = pd.DataFrame(
            {
                "X": np.linspace(0, 10, 50),
                "Y_strong": np.linspace(0, 10, 50)
                + np.random.normal(0, 0.1, 50),  # Very strong correlation
                "Y_weak": np.random.normal(5, 2, 50),  # No correlation
            }
        )

        result = self.pairwise_tests.pearson_correlation_pairwise_test(strong_corr_df)

        # Should detect significant correlations
        self.assertGreater(result.details.significant_comparisons, 0)
        self.assertIn("significant", result.result_text.lower())

    def test_error_handling_insufficient_columns(self):
        """Test error handling when DataFrame has insufficient columns."""
        single_col_df = pd.DataFrame({"OnlyCol": [1, 2, 3, 4, 5]})

        with self.assertRaises(ValueError) as context:
            self.pairwise_tests.student_independent_pairwise_test(single_col_df)

        self.assertIn("at least two columns", str(context.exception))

    def test_error_handling_invalid_reference_column(self):
        """Test error handling when reference column doesn't exist."""
        with self.assertRaises(ValueError) as context:
            self.pairwise_tests.student_independent_pairwise_test(
                self.test_df, reference_column="NonExistent"
            )

        self.assertIn("not found in dataframe columns", str(context.exception))

    def test_error_handling_no_valid_pairs(self):
        """Test error handling when no valid pairs exist."""
        # Create DataFrame with all NaN except diagonal
        empty_df = pd.DataFrame(
            {"A": [1, np.nan, np.nan], "B": [np.nan, 2, np.nan], "C": [np.nan, np.nan, 3]}
        )

        with self.assertRaises(ValueError) as context:
            self.pairwise_tests.student_independent_pairwise_test(empty_df)

        self.assertIn("No valid pairs", str(context.exception))

    def test_matrix_symmetry_without_reference(self):
        """Test that pairwise comparison matrices are symmetric when no reference is used."""
        result = self.pairwise_tests.pearson_correlation_pairwise_test(self.correlation_df)
        matrix = result.details.pairwise_comparisons_matrix

        # Check symmetry for non-null values
        for i in matrix.index:
            for j in matrix.columns:
                if pd.notna(matrix.loc[i, j]) and pd.notna(matrix.loc[j, i]):
                    self.assertAlmostEqual(matrix.loc[i, j], matrix.loc[j, i], places=10)

    def test_small_dataset_handling(self):
        """Test handling of small datasets."""
        result = self.pairwise_tests.student_independent_pairwise_test(self.small_df)

        self.assertIsInstance(result, AiTableStatsResults)
        self.assertIsInstance(result.details, StudentTTestPairwiseDetails)

        # Should work with small datasets
        self.assertGreater(result.details.total_comparisons, 0)

    def test_result_text_format(self):
        """Test that result texts are properly formatted."""
        result = self.pairwise_tests.student_independent_pairwise_test(self.test_df)

        # Result text should contain key information
        self.assertIn("pairwise", result.result_text.lower())
        self.assertTrue(
            "significant" in result.result_text.lower()
            or "no significant" in result.result_text.lower()
        )

    def test_details_attributes(self):
        """Test that all required details attributes are present."""
        result = self.pairwise_tests.pearson_correlation_pairwise_test(self.correlation_df)

        details = result.details
        self.assertTrue(hasattr(details, "pairwise_comparisons_matrix"))
        self.assertTrue(hasattr(details, "significant_comparisons"))
        self.assertTrue(hasattr(details, "total_comparisons"))

        self.assertIsInstance(details.pairwise_comparisons_matrix, pd.DataFrame)
        self.assertIsInstance(details.significant_comparisons, int)
        self.assertIsInstance(details.total_comparisons, int)
