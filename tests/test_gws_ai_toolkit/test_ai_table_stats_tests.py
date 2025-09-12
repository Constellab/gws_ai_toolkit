from unittest import TestCase
from unittest.mock import patch

import numpy as np
import pandas as pd

from gws_ai_toolkit.stats.ai_table_stats_tests import AiTableStatsTests
from gws_ai_toolkit.stats.ai_table_stats_type import (
    AiTableStatsResults, AnovaTestDetails, BonferroniTestDetails,
    ChiSquaredAdjustmentTestDetails, ChiSquaredIndependenceTestDetails,
    DunnTestDetails, FriedmanTestDetails, HomogeneityTestDetails,
    McNemarTestDetails, MultiGroupNonParametricTestDetails,
    NormalityTestDetails, PairedNonParametricTestDetails, ScheffeTestDetails,
    StudentTTestIndependentDetails, StudentTTestPairedDetails,
    TukeyHSDTestDetails, TwoGroupNonParametricTestDetails)


# test_ai_table_stats_tests.py
class TestAiTableStatsTests(TestCase):
    """Unit tests for AiTableStatsTests class."""

    def setUp(self):
        """Set up test fixtures."""
        self.stats_tests = AiTableStatsTests()

        # Common test data
        self.normal_data = np.random.normal(0, 1, 100)
        self.non_normal_data = np.random.exponential(2, 100)
        self.group1 = np.random.normal(0, 1, 50)
        self.group2 = np.random.normal(1, 1, 50)
        self.group3 = np.random.normal(2, 1, 50)

        # Paired data
        self.paired_data1 = np.random.normal(0, 1, 30)
        self.paired_data2 = self.paired_data1 + np.random.normal(0.5, 0.2, 30)

        # Contingency table for chi-squared tests
        self.contingency_table = [[10, 10, 20], [20, 20, 40]]
        self.mcnemar_table = [[10, 5], [8, 12]]

        # Observed frequencies for chi-squared adjustment
        self.observed_freq = [15, 25, 30, 20, 10]

    def test_shapiro_wilk_test_normal_data(self):
        """Test Shapiro-Wilk test with normal data."""
        result = self.stats_tests.shapiro_wilk_test(self.normal_data)

        self.assertIsInstance(result, AiTableStatsResults)
        self.assertEqual(result.test_name, 'Shapiro-Wilk')
        self.assertIsInstance(result.statistic, float)
        self.assertIsInstance(result.p_value, float)
        self.assertIsInstance(result.details, NormalityTestDetails)
        self.assertEqual(result.details.sample_size, len(self.normal_data))
        self.assertIn("normal", result.result_text.lower())

    def test_shapiro_wilk_test_non_normal_data(self):
        """Test Shapiro-Wilk test with non-normal data."""
        # Use clearly non-normal data
        heavily_skewed_data = np.random.exponential(0.1, 50)
        result = self.stats_tests.shapiro_wilk_test(heavily_skewed_data)

        self.assertIsInstance(result, AiTableStatsResults)
        self.assertEqual(result.test_name, 'Shapiro-Wilk')
        self.assertIsInstance(result.statistic, float)
        self.assertIsInstance(result.p_value, float)

    def test_kolmogorov_smirnov_test(self):
        """Test Kolmogorov-Smirnov test."""
        result = self.stats_tests.kolmogorov_smirnov_test(self.normal_data)

        self.assertIsInstance(result, AiTableStatsResults)
        self.assertEqual(result.test_name, 'Kolmogorov-Smirnov (Lilliefors)')
        self.assertIsInstance(result.statistic, float)
        self.assertIsInstance(result.p_value, float)
        self.assertIsInstance(result.details, NormalityTestDetails)
        self.assertEqual(result.details.sample_size, len(self.normal_data))

    def test_bartlett_test(self):
        """Test Bartlett's test for homogeneity of variances."""
        result = self.stats_tests.bartlett_test(self.group1, self.group2, self.group3)

        self.assertIsInstance(result, AiTableStatsResults)
        self.assertEqual(result.test_name, 'Bartlett')
        self.assertIsInstance(result.statistic, float)
        self.assertIsInstance(result.p_value, float)
        self.assertIsInstance(result.details, HomogeneityTestDetails)
        self.assertEqual(result.details.groups_count, 3)
        self.assertIn("variance", result.result_text.lower())

    def test_levene_test(self):
        """Test Levene's test for homogeneity of variances."""
        result = self.stats_tests.levene_test(self.group1, self.group2)

        self.assertIsInstance(result, AiTableStatsResults)
        self.assertEqual(result.test_name, 'Levene')
        self.assertIsInstance(result.statistic, float)
        self.assertIsInstance(result.p_value, float)
        self.assertIsInstance(result.details, HomogeneityTestDetails)
        self.assertEqual(result.details.groups_count, 2)

    def test_chi2_adjustment_test(self):
        """Test Chi-squared goodness of fit test."""
        result = self.stats_tests.chi2_adjustment_test(self.observed_freq)

        self.assertIsInstance(result, AiTableStatsResults)
        self.assertEqual(result.test_name, 'Chi-squared adjustment')
        self.assertIsInstance(result.statistic, float)
        self.assertIsInstance(result.p_value, float)
        self.assertIsInstance(result.details, ChiSquaredAdjustmentTestDetails)
        self.assertEqual(result.details.categories, len(self.observed_freq))
        self.assertEqual(len(result.details.expected_freq), len(self.observed_freq))

    def test_chi2_independence_test(self):
        """Test Chi-squared test of independence."""
        result = self.stats_tests.chi2_independence_test(self.contingency_table)

        self.assertIsInstance(result, AiTableStatsResults)
        self.assertEqual(result.test_name, 'Chi-squared independence')
        self.assertIsInstance(result.statistic, float)
        self.assertIsInstance(result.p_value, float)
        self.assertIsInstance(result.details, ChiSquaredIndependenceTestDetails)
        self.assertIsInstance(result.details.degrees_of_freedom, int)
        self.assertIsInstance(result.details.expected_frequencies, list)
        self.assertEqual(result.details.raw_data, self.contingency_table)

    def test_mcnemar_test(self):
        """Test McNemar's test for paired categorical data."""
        result = self.stats_tests.mcnemar_test(self.mcnemar_table)

        self.assertIsInstance(result, AiTableStatsResults)
        self.assertEqual(result.test_name, 'McNemar')
        self.assertIsInstance(result.statistic, float)
        self.assertIsInstance(result.p_value, float)
        self.assertIsInstance(result.details, McNemarTestDetails)

    def test_student_independent_test(self):
        """Test Student's t-test for independent samples."""
        result = self.stats_tests.student_independent_test(self.group1, self.group2)

        self.assertIsInstance(result, AiTableStatsResults)
        self.assertEqual(result.test_name, 'Student t-test (independent)')
        self.assertIsInstance(result.statistic, float)
        self.assertIsInstance(result.p_value, float)
        self.assertIsInstance(result.details, StudentTTestIndependentDetails)
        self.assertEqual(result.details.sample_sizes, [len(self.group1), len(self.group2)])
        self.assertIsInstance(result.details.degrees_of_freedom, (int, float))

    def test_student_paired_test(self):
        """Test Student's t-test for paired samples."""
        result = self.stats_tests.student_paired_test(self.paired_data1, self.paired_data2)

        self.assertIsInstance(result, AiTableStatsResults)
        self.assertEqual(result.test_name, 'Student t-test (paired)')
        self.assertIsInstance(result.statistic, float)
        self.assertIsInstance(result.p_value, float)
        self.assertIsInstance(result.details, StudentTTestPairedDetails)
        self.assertEqual(result.details.pairs_count, len(self.paired_data1))

    def test_anova_test(self):
        """Test ANOVA test."""
        result = self.stats_tests.anova_test(self.group1, self.group2, self.group3)

        self.assertIsInstance(result, AiTableStatsResults)
        self.assertEqual(result.test_name, 'ANOVA')
        self.assertIsInstance(result.statistic, float)
        self.assertIsInstance(result.p_value, float)
        self.assertIsInstance(result.details, AnovaTestDetails)
        self.assertEqual(result.details.groups_count, 3)
        self.assertEqual(result.details.total_observations, len(self.group1) + len(self.group2) + len(self.group3))

    def test_mann_whitney_test(self):
        """Test Mann-Whitney test."""
        result = self.stats_tests.mann_whitney_test(self.group1, self.group2)

        self.assertIsInstance(result, AiTableStatsResults)
        self.assertEqual(result.test_name, 'Mann-Whitney')
        self.assertIsInstance(result.statistic, float)
        self.assertIsInstance(result.p_value, float)
        self.assertIsInstance(result.details, TwoGroupNonParametricTestDetails)
        self.assertEqual(result.details.sample_sizes, [len(self.group1), len(self.group2)])

    def test_wilcoxon_test(self):
        """Test Wilcoxon signed-rank test for paired samples."""
        result = self.stats_tests.wilcoxon_test(self.paired_data1, self.paired_data2)

        self.assertIsInstance(result, AiTableStatsResults)
        self.assertEqual(result.test_name, 'Wilcoxon signed-rank')
        self.assertIsInstance(result.statistic, float)
        self.assertIsInstance(result.p_value, float)
        self.assertIsInstance(result.details, PairedNonParametricTestDetails)
        self.assertEqual(result.details.pairs_count, len(self.paired_data1))

    def test_kruskal_wallis_test(self):
        """Test Kruskal-Wallis H test."""
        result = self.stats_tests.kruskal_wallis_test(self.group1, self.group2, self.group3)

        self.assertIsInstance(result, AiTableStatsResults)
        self.assertEqual(result.test_name, 'Kruskal-Wallis')
        self.assertIsInstance(result.statistic, float)
        self.assertIsInstance(result.p_value, float)
        self.assertIsInstance(result.details, MultiGroupNonParametricTestDetails)
        self.assertEqual(result.details.groups_count, 3)
        self.assertEqual(result.details.total_observations, len(self.group1) + len(self.group2) + len(self.group3))

    def test_friedman_test(self):
        """Test Friedman test for repeated measures."""
        result = self.stats_tests.friedman_test(self.group1[:30], self.group2[:30], self.group3[:30])

        self.assertIsInstance(result, AiTableStatsResults)
        self.assertEqual(result.test_name, 'Friedman')
        self.assertIsInstance(result.statistic, float)
        self.assertIsInstance(result.p_value, float)
        self.assertIsInstance(result.details, FriedmanTestDetails)
        self.assertEqual(result.details.conditions_count, 3)
        self.assertEqual(result.details.subjects_count, 30)

    def test_pearson_correlation_test(self):
        """Test Pearson correlation test."""
        x = np.random.normal(0, 1, 50)
        y = 0.5 * x + np.random.normal(0, 0.5, 50)  # Create some correlation

        result = self.stats_tests.pearson_correlation_test(x, y)

        self.assertIsInstance(result, AiTableStatsResults)
        self.assertEqual(result.test_name, 'Pearson correlation')
        self.assertIsInstance(result.statistic, float)
        self.assertIsInstance(result.p_value, float)
        self.assertIsInstance(result.details, TwoGroupNonParametricTestDetails)
        self.assertEqual(result.details.sample_sizes, [len(x), len(y)])
        self.assertIn("correlation", result.result_text.lower())

    def test_spearman_correlation_test(self):
        """Test Spearman rank correlation test."""
        x = np.random.normal(0, 1, 50)
        y = 0.5 * x + np.random.normal(0, 0.5, 50)  # Create some correlation

        result = self.stats_tests.spearman_correlation_test(x, y)

        self.assertIsInstance(result, AiTableStatsResults)
        self.assertEqual(result.test_name, 'Spearman correlation')
        self.assertIsInstance(result.statistic, float)
        self.assertIsInstance(result.p_value, float)
        self.assertIsInstance(result.details, TwoGroupNonParametricTestDetails)
        self.assertEqual(result.details.sample_sizes, [len(x), len(y)])
        self.assertIn("correlation", result.result_text.lower())

    def test_tukey_hsd_test(self):
        """Test Tukey's HSD post-hoc test."""
        # Create DataFrame with different groups
        df = pd.DataFrame({
            'Group_A': np.random.normal(0, 1, 30),
            'Group_B': np.random.normal(1, 1, 30),
            'Group_C': np.random.normal(2, 1, 30)
        })

        result = self.stats_tests.tukey_hsd_test(df)

        self.assertIsInstance(result, AiTableStatsResults)
        self.assertEqual(result.test_name, 'Tukey HSD')
        self.assertIsInstance(result.details, TukeyHSDTestDetails)
        self.assertIsInstance(result.details.summary, str)
        self.assertIsInstance(result.details.pairwise_comparisons, list)
        self.assertIsInstance(result.details.significant_pairs, list)
        self.assertIn("pairwise", result.result_text.lower())

    def test_dunn_test(self):
        """Test Dunn's post-hoc test."""
        # Create DataFrame with different groups
        df = pd.DataFrame({
            'Group_A': np.random.normal(0, 1, 30),
            'Group_B': np.random.normal(1, 1, 30),
            'Group_C': np.random.normal(2, 1, 30)
        })

        result = self.stats_tests.dunn_test(df)

        self.assertIsInstance(result, AiTableStatsResults)
        self.assertEqual(result.test_name, 'Dunn')
        self.assertIsInstance(result.details, DunnTestDetails)
        self.assertIsInstance(result.details.pairwise_matrix, dict)
        self.assertEqual(result.details.adjustment_method, 'bonferroni')
        self.assertIsInstance(result.details.significant_comparisons, int)
        self.assertIn("pairwise", result.result_text.lower())

    def test_bonferroni_test_with_list(self):
        """Test Bonferroni correction with list of p-values."""
        p_values = [0.01, 0.03, 0.05, 0.1, 0.2]
        result = self.stats_tests.bonferroni_test(p_values)

        self.assertIsInstance(result, AiTableStatsResults)
        self.assertEqual(result.test_name, 'Student t-test (independent paired wise)')
        self.assertIsInstance(result.details, BonferroniTestDetails)
        self.assertEqual(result.details.original_p_values, p_values)
        self.assertEqual(len(result.details.corrected_p_values), len(p_values))
        self.assertEqual(result.details.adjustment_method, 'bonferroni')
        self.assertEqual(result.details.total_comparisons, len(p_values))
        self.assertIsInstance(result.details.corrected_alpha, float)
        self.assertIn("bonferroni", result.result_text.lower())

    def test_bonferroni_test_with_dataframe(self):
        """Test Bonferroni correction with DataFrame of p-values."""
        p_values_df = pd.DataFrame({'p_vals': [0.01, 0.03, 0.05, 0.1, 0.2]})
        result = self.stats_tests.bonferroni_test(p_values_df)

        self.assertIsInstance(result, AiTableStatsResults)
        self.assertIsInstance(result.details, BonferroniTestDetails)
        self.assertEqual(len(result.details.original_p_values), 5)

    def test_bonferroni_test_with_series(self):
        """Test Bonferroni correction with Series of p-values."""
        p_values_series = pd.Series([0.01, 0.03, 0.05, 0.1, 0.2])
        result = self.stats_tests.bonferroni_test(p_values_series)

        self.assertIsInstance(result, AiTableStatsResults)
        self.assertIsInstance(result.details, BonferroniTestDetails)
        self.assertEqual(len(result.details.original_p_values), 5)

    def test_scheffe_test_with_list(self):
        """Test Scheffe correction with list of p-values."""
        p_values = [0.01, 0.03, 0.05, 0.1, 0.2]
        num_groups = 3
        result = self.stats_tests.scheffe_test(p_values, num_groups)

        self.assertIsInstance(result, AiTableStatsResults)
        self.assertEqual(result.test_name, 'Student t-test (independent paired wise)')
        self.assertIsInstance(result.details, ScheffeTestDetails)
        self.assertEqual(result.details.original_p_values, p_values)
        self.assertEqual(len(result.details.corrected_p_values), len(p_values))
        self.assertEqual(result.details.adjustment_method, 'scheffe')
        self.assertEqual(result.details.num_groups, num_groups)
        self.assertIsInstance(result.details.scheffe_multiplier, float)
        self.assertIn("scheffe", result.result_text.lower())

    def test_scheffe_test_invalid_groups(self):
        """Test Scheffe correction with invalid number of groups."""
        p_values = [0.01, 0.03, 0.05]
        with self.assertRaises(ValueError) as context:
            self.stats_tests.scheffe_test(p_values, 1)
        self.assertIn("at least 2", str(context.exception))

    def test_input_type_flexibility(self):
        """Test that methods accept various input types (numpy arrays, pandas Series, lists)."""
        # Test with numpy array
        result_np = self.stats_tests.shapiro_wilk_test(np.array([1, 2, 3, 4, 5]))

        # Test with pandas Series
        result_pd = self.stats_tests.shapiro_wilk_test(pd.Series([1, 2, 3, 4, 5]))

        # Test with list
        result_list = self.stats_tests.shapiro_wilk_test([1, 2, 3, 4, 5])

        # All should return valid results
        for result in [result_np, result_pd, result_list]:
            self.assertIsInstance(result, AiTableStatsResults)
            self.assertEqual(result.test_name, 'Shapiro-Wilk')

    def test_result_text_interpretation(self):
        """Test that result texts are correctly interpreted based on p-values."""
        # Create data that should have significantly different means
        group_low = np.full(50, 0)
        group_high = np.full(50, 10)

        result = self.stats_tests.student_independent_test(group_low, group_high)

        # Should detect significant difference
        self.assertLess(result.p_value, 0.05)
        self.assertIn("significant", result.result_text.lower())

    def test_empty_input_handling(self):
        """Test handling of edge cases with empty or minimal data."""
        # Test with minimal data that should still work
        minimal_data = [1, 2, 3]
        result = self.stats_tests.shapiro_wilk_test(minimal_data)

        self.assertIsInstance(result, AiTableStatsResults)
        self.assertEqual(result.details.sample_size, 3)
