
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd
import plotly.graph_objs as go
from gws_core import BaseModelDTO
from scikit_posthocs import posthoc_dunn
from scipy import stats
from scipy.stats import f_oneway
from statsmodels.stats.contingency_tables import mcnemar
from statsmodels.stats.diagnostic import lilliefors
from statsmodels.stats.multicomp import MultiComparison
from statsmodels.stats.weightstats import ttest_ind


class AiTableStatsResults(BaseModelDTO):

    test_name: str
    result_text: str
    result_figure: Optional[str] = None
    statistic: Optional[Decimal] = None
    p_value: Optional[Decimal] = None
    details: Optional[Dict[str, Any]] = None

    p_value_scientific: Optional[str] = None
    statistic_scientific: Optional[str] = None

    def __init__(self, **data: Any):
        super().__init__(**data)
        if self.p_value is not None:
            self.p_value_scientific = f"{self.p_value:.2e}"
        if self.statistic is not None:
            self.statistic_scientific = f"{self.statistic:.2e}"

    # class Config:
    #     arbitrary_types_allowed = True


class AiTableStatsTests:
    """Class containing all statistical tests for AI Table Stats analysis."""

    # Normality tests
    def shapiro_wilk_test(self, data: Union[np.ndarray, pd.Series, List[float]]) -> AiTableStatsResults:
        """Shapiro-Wilk normality test."""
        statistic, p_value = stats.shapiro(data)

        # Generate result text based on p-value
        if p_value < 0.05:
            result_text = "Data significantly deviates from normal distribution."
        else:
            result_text = "Data appears to follow a normal distribution."

        return AiTableStatsResults(
            test_name='Shapiro-Wilk',
            result_text=result_text,
            result_figure=None,
            statistic=Decimal(statistic),
            p_value=Decimal(p_value),
            details={
                'interpretation': 'Test for normality assumption',
                'null_hypothesis': 'Data follows normal distribution',
                'sample_size': len(data)
            }
        )

    def kolmogorov_smirnov_test(self, data: Union[np.ndarray, pd.Series, List[float]]) -> AiTableStatsResults:
        """Kolmogorov-Smirnov normality test using Lilliefors from statsmodels."""
        statistic, p_value = lilliefors(data, dist='norm')

        # Generate result text based on p-value
        if p_value < 0.05:
            result_text = "Data significantly deviates from normal distribution."
        else:
            result_text = "Data appears to follow a normal distribution."

        return AiTableStatsResults(
            test_name='Kolmogorov-Smirnov (Lilliefors)',
            result_text=result_text,
            result_figure=None,
            statistic=Decimal(statistic),
            p_value=Decimal(p_value),
            details={
                'interpretation': 'Test for normality assumption using Lilliefors correction',
                'null_hypothesis': 'Data follows normal distribution',
                'sample_size': len(data)
            }
        )

    # Homogeneity tests
    def bartlett_test(self, *groups: Union[np.ndarray, pd.Series, List[float]]) -> AiTableStatsResults:
        """Bartlett's test for homogeneity of variances."""
        statistic, p_value = stats.bartlett(*groups)

        # Generate result text based on p-value
        if p_value < 0.05:
            result_text = "Groups have significantly different variances."
        else:
            result_text = "Groups have similar variances (homogeneity assumption met)."

        return AiTableStatsResults(
            test_name='Bartlett',
            result_text=result_text,
            result_figure=None,
            statistic=Decimal(statistic),
            p_value=Decimal(p_value),
            details={
                'interpretation': 'Test for homogeneity of variances',
                'null_hypothesis': 'All groups have equal variances',
                'groups_count': len(groups)
            }
        )

    def levene_test(self, *groups: Union[np.ndarray, pd.Series, List[float]]) -> AiTableStatsResults:
        """Levene's test for homogeneity of variances."""
        statistic, p_value = stats.levene(*groups)

        # Generate result text based on p-value
        if p_value < 0.05:
            result_text = "Groups have significantly different variances."
        else:
            result_text = "Groups have similar variances (homogeneity assumption met)."

        return AiTableStatsResults(
            test_name='Levene',
            result_text=result_text,
            result_figure=None,
            statistic=Decimal(statistic),
            p_value=Decimal(p_value),
            details={
                'interpretation': 'Test for homogeneity of variances (robust alternative to Bartlett)',
                'null_hypothesis': 'All groups have equal variances',
                'groups_count': len(groups)
            }
        )

    # Qualitative tests
    def chi2_adjustment_test(self, observed_freq: Union[np.ndarray, List[int]]) -> AiTableStatsResults:
        """Chi-squared goodness of fit test (adjustment test)."""
        # For goodness of fit, we compare observed vs expected uniform distribution
        expected_freq = np.full_like(observed_freq, np.mean(observed_freq))
        statistic, p_value = stats.chisquare(observed_freq, expected_freq)

        # Generate result text based on p-value
        if p_value < 0.05:
            result_text = "Observed frequencies significantly deviate from expected distribution."
        else:
            result_text = "Observed frequencies fit the expected distribution well."

        return AiTableStatsResults(
            test_name='Chi-squared adjustment',
            result_text=result_text,
            result_figure=None,
            statistic=Decimal(statistic),
            p_value=Decimal(p_value),
            details={
                'interpretation': 'Goodness of fit test for uniform distribution',
                'null_hypothesis': 'Observed frequencies follow expected distribution',
                'categories': len(observed_freq),
                'expected_freq': expected_freq.tolist()
            }
        )

    def chi2_independence_test(self, contingency_table: Union[np.ndarray, List[List[int]]]) -> AiTableStatsResults:
        """Chi-squared test of independence."""
        chi2_stat, p_value, dof, expected = stats.chi2_contingency(contingency_table)

        # Generate result text based on p-value
        if Decimal(p_value) < 0.05:
            result_text = "Variables are significantly associated (not independent)."
        else:
            result_text = "Variables appear to be independent."

        return AiTableStatsResults(
            test_name='Chi-squared independence',
            result_text=result_text,
            result_figure=None,
            statistic=Decimal(chi2_stat),
            p_value=Decimal(p_value),
            details={
                'interpretation': 'Test of independence between categorical variables',
                'null_hypothesis': 'Variables are independent',
                'degrees_of_freedom': int(dof),
                'expected_frequencies': expected.tolist()
            }
        )

    def mcnemar_test(self, table: Union[np.ndarray, List[List[int]]]) -> AiTableStatsResults:
        """McNemar's test for paired categorical data."""
        result = mcnemar(table, exact=False, correction=True)

        # Generate result text based on p-value
        if Decimal(result.pvalue) < 0.05:
            result_text = "Significant difference between paired categorical responses."
        else:
            result_text = "No significant difference between paired responses."

        return AiTableStatsResults(
            test_name='McNemar',
            result_text=result_text,
            result_figure=None,
            statistic=Decimal(result.statistic),
            p_value=Decimal(result.pvalue),
            details={
                'interpretation': 'Test for paired categorical data differences',
                'null_hypothesis': 'Marginal probabilities are equal',
                'table_shape': np.array(table).shape
            }
        )

    # Quantitative tests - parametric
    def student_independent_test(self, group1: Union[np.ndarray, pd.Series, List[float]],
                                 group2: Union[np.ndarray, pd.Series, List[float]]) -> AiTableStatsResults:
        """Student's t-test for independent samples."""

        statistic, p_value, df = ttest_ind(group1, group2, usevar='pooled')

        # Generate result text based on p-value
        if p_value < 0.05:
            result_text = "Significant difference between group means."
        else:
            result_text = "No significant difference between group means."

        return AiTableStatsResults(
            test_name='Student t-test (independent)',
            result_text=result_text,
            result_figure=None,
            statistic=Decimal(statistic),
            p_value=Decimal(p_value),
            details={
                'interpretation': 'Compare means of two independent groups',
                'null_hypothesis': 'Group means are equal',
                'degrees_of_freedom': df,
                'sample_sizes': [len(group1), len(group2)]
            }
        )

    def student_paired_test(self, group1: Union[np.ndarray, pd.Series, List[float]],
                            group2: Union[np.ndarray, pd.Series, List[float]]) -> AiTableStatsResults:
        """Student's t-test for paired samples."""
        statistic, p_value = stats.ttest_rel(group1, group2)

        # Generate result text based on p-value
        if Decimal(p_value) < 0.05:
            result_text = "Significant difference between paired measurements."
        else:
            result_text = "No significant difference between paired measurements."

        return AiTableStatsResults(
            test_name='Student t-test (paired)',
            result_text=result_text,
            result_figure=None,
            statistic=Decimal(statistic),
            p_value=Decimal(p_value),
            details={
                'interpretation': 'Compare means of paired/dependent samples',
                'null_hypothesis': 'Mean difference equals zero',
                'pairs_count': len(group1)
            }
        )

    def anova_test(self, *groups: Union[np.ndarray, pd.Series, List[float]]) -> AiTableStatsResults:
        """ANOVA test using scipy.stats."""
        # Use f_oneway with column arrays directly
        statistic, p_value = f_oneway(*groups)

        # Generate result text based on p-value
        if p_value < 0.05:
            result_text = "Significant differences found between group means."
        else:
            result_text = "No significant differences between group means."

        return AiTableStatsResults(
            test_name='ANOVA',
            result_text=result_text,
            result_figure=None,
            statistic=Decimal(statistic),
            p_value=Decimal(p_value),
            details={
                'interpretation': 'Compare means across multiple groups',
                'null_hypothesis': 'All group means are equal',
                'groups_count': len(groups),
                'total_observations': sum(len(group) for group in groups)
            }
        )

    # Quantitative tests - non-parametric
    def mann_whitney_test(self, group1: Union[np.ndarray, pd.Series, List[float]],
                          group2: Union[np.ndarray, pd.Series, List[float]]) -> AiTableStatsResults:
        """Mann-Whitney U test."""
        statistic, p_value = stats.mannwhitneyu(group1, group2, alternative='two-sided')

        # Generate result text based on p-value
        if p_value < 0.05:
            result_text = "Significant difference between group distributions."
        else:
            result_text = "No significant difference between group distributions."

        return AiTableStatsResults(
            test_name='Mann-Whitney U',
            result_text=result_text,
            result_figure=None,
            statistic=Decimal(statistic),
            p_value=Decimal(p_value),
            details={
                'interpretation': 'Non-parametric test comparing two independent groups',
                'null_hypothesis': 'Distributions are identical',
                'sample_sizes': [len(group1), len(group2)]
            }
        )

    def wilcoxon_test(self, group1: Union[np.ndarray, pd.Series, List[float]],
                      group2: Union[np.ndarray, pd.Series, List[float]]) -> AiTableStatsResults:
        """Wilcoxon signed-rank test for paired samples."""
        statistic, p_value = stats.wilcoxon(group1, group2, alternative='two-sided')

        # Generate result text based on p-value
        if Decimal(p_value) < 0.05:
            result_text = "Significant difference between paired observations."
        else:
            result_text = "No significant difference between paired observations."

        return AiTableStatsResults(
            test_name='Wilcoxon signed-rank',
            result_text=result_text,
            result_figure=None,
            statistic=Decimal(statistic),
            p_value=Decimal(p_value),
            details={
                'interpretation': 'Non-parametric test for paired samples',
                'null_hypothesis': 'Median difference equals zero',
                'pairs_count': len(group1)
            }
        )

    def kruskal_wallis_test(self, *groups: Union[np.ndarray, pd.Series, List[float]]) -> AiTableStatsResults:
        """Kruskal-Wallis H test."""
        statistic, p_value = stats.kruskal(*groups)

        # Generate result text based on p-value
        if p_value < 0.05:
            result_text = "Significant differences found between group distributions."
        else:
            result_text = "No significant differences between group distributions."

        return AiTableStatsResults(
            test_name='Kruskal-Wallis',
            result_text=result_text,
            result_figure=None,
            statistic=Decimal(statistic),
            p_value=Decimal(p_value),
            details={
                'interpretation': 'Non-parametric test comparing multiple groups',
                'null_hypothesis': 'All group distributions are identical',
                'groups_count': len(groups),
                'total_observations': sum(len(group) for group in groups)
            }
        )

    def friedman_test(self, *groups: Union[np.ndarray, pd.Series, List[float]]) -> AiTableStatsResults:
        """Friedman test for repeated measures."""
        statistic, p_value = stats.friedmanchisquare(*groups)

        # Generate result text based on p-value
        if p_value < 0.05:
            result_text = "Significant differences found in repeated measures."
        else:
            result_text = "No significant differences in repeated measures."

        return AiTableStatsResults(
            test_name='Friedman',
            result_text=result_text,
            result_figure=None,
            statistic=Decimal(statistic),
            p_value=Decimal(p_value),
            details={
                'interpretation': 'Non-parametric test for repeated measures',
                'null_hypothesis': 'All conditions have identical effects',
                'conditions_count': len(groups),
                'subjects_count': len(groups[0]) if groups else 0
            }
        )

    # Post-hoc tests
    def tukey_hsd_test(self, dataframe: pd.DataFrame) -> AiTableStatsResults:
        """Tukey's HSD post-hoc test after ANOVA."""

        # Melt the dataframe to create group and value columns
        melted_df = pd.melt(dataframe, var_name="group", value_name="value").dropna()

        # Use MultiComparison class
        mc = MultiComparison(melted_df["value"], melted_df["group"])
        tukey_result = mc.tukeyhsd(alpha=0.05)

        # Check if any comparisons are significant
        significant_pairs = []
        for row in tukey_result.summary().data[1:]:  # Skip header
            if row[5] == 'True':  # reject column
                significant_pairs.append(f"{row[0]} vs {row[1]}")

        if significant_pairs:
            result_text = f"Significant differences found in {len(significant_pairs)} pairwise comparisons."
        else:
            result_text = "No significant pairwise differences found."

        return AiTableStatsResults(
            test_name='Tukey HSD',
            result_text=result_text,
            result_figure=None,
            statistic=None,
            p_value=None,
            details={
                'interpretation': 'Post-hoc test following significant ANOVA',
                'summary': str(tukey_result),
                'pairwise_comparisons': tukey_result.summary().data,
                'significant_pairs': significant_pairs
            }
        )

    def dunn_test(self, dataframe: pd.DataFrame) -> AiTableStatsResults:
        """Dunn's post-hoc test after Kruskal-Wallis."""
        try:
            # Melt the dataframe to create group and value columns
            melted_df = pd.melt(dataframe, var_name="group", value_name="value").dropna()

            dunn_result = posthoc_dunn(melted_df, val_col='value', group_col='group', p_adjust='bonferroni')

            # Count significant comparisons (p < 0.05)
            significant_count = 0
            for i in dunn_result.index:
                for j in dunn_result.columns:
                    if i != j:
                        p_val = dunn_result.loc[i, j]
                        if pd.notna(p_val) and Decimal(p_val) < 0.05:
                            significant_count += 1
            significant_count = significant_count // 2  # Each comparison counted twice

            if significant_count > 0:
                result_text = f"Significant differences found in {significant_count} pairwise comparisons."
            else:
                result_text = "No significant pairwise differences found."

            return AiTableStatsResults(
                test_name='Dunn',
                result_text=result_text,
                result_figure=None,
                statistic=None,
                p_value=None,
                details={
                    'interpretation': 'Post-hoc test following significant Kruskal-Wallis',
                    'pairwise_matrix': dunn_result.to_dict(),
                    'adjustment_method': 'bonferroni',
                    'significant_comparisons': significant_count
                }
            )
        except Exception as e:
            return AiTableStatsResults(
                test_name='Dunn (error)',
                result_text=f"Error running Dunn test: {str(e)}",
                result_figure=None,
                statistic=None,
                p_value=None,
                details={
                    'error': str(e),
                    'interpretation': 'Test failed to execute'
                }
            )
