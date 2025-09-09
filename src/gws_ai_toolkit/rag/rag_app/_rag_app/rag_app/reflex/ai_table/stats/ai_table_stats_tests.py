
import numpy as np
import pandas as pd
from scikit_posthocs import posthoc_dunn
from scipy import stats
from scipy.stats import f_oneway
from statsmodels.stats.contingency_tables import mcnemar
from statsmodels.stats.diagnostic import lilliefors
from statsmodels.stats.multicomp import MultiComparison
from statsmodels.stats.weightstats import ttest_ind


class AiTableStatsTests:
    """Class containing all statistical tests for AI Table Stats analysis."""

    def __init__(self):
        pass

    # Normality tests
    def shapiro_wilk_test(self, data):
        """Shapiro-Wilk normality test."""
        statistic, p_value = stats.shapiro(data)
        return {
            'statistic': statistic,
            'p_value': p_value,
            'test_name': 'Shapiro-Wilk'
        }

    def kolmogorov_smirnov_test(self, data):
        """Kolmogorov-Smirnov normality test using Lilliefors from statsmodels."""
        statistic, p_value = lilliefors(data, dist='norm')
        return {
            'statistic': statistic,
            'p_value': p_value,
            'test_name': 'Kolmogorov-Smirnov (Lilliefors)'
        }

    # Homogeneity tests
    def bartlett_test(self, *groups):
        """Bartlett's test for homogeneity of variances."""
        statistic, p_value = stats.bartlett(*groups)
        return {
            'statistic': statistic,
            'p_value': p_value,
            'test_name': 'Bartlett'
        }

    def levene_test(self, *groups):
        """Levene's test for homogeneity of variances."""
        statistic, p_value = stats.levene(*groups)
        return {
            'statistic': statistic,
            'p_value': p_value,
            'test_name': 'Levene'
        }

    # Qualitative tests
    def chi2_adjustment_test(self, observed_freq):
        """Chi-squared goodness of fit test (adjustment test)."""
        # For goodness of fit, we compare observed vs expected uniform distribution
        expected_freq = np.full_like(observed_freq, np.mean(observed_freq))
        statistic, p_value = stats.chisquare(observed_freq, expected_freq)
        return {
            'statistic': statistic,
            'p_value': p_value,
            'test_name': 'Chi-squared adjustment'
        }

    def chi2_independence_test(self, contingency_table):
        """Chi-squared test of independence."""
        chi2_stat, p_value, dof, expected = stats.chi2_contingency(contingency_table)
        return {
            'statistic': chi2_stat,
            'p_value': p_value,
            'dof': dof,
            'expected': expected,
            'test_name': 'Chi-squared independence'
        }

    def mcnemar_test(self, table):
        """McNemar's test for paired categorical data."""
        result = mcnemar(table, exact=False, correction=True)
        return {
            'statistic': result.statistic,
            'p_value': result.pvalue,
            'test_name': 'McNemar'
        }

    # Quantitative tests - parametric
    def student_independent_test(self, group1, group2):
        """Student's t-test for independent samples."""
        statistic, p_value, df = ttest_ind(group1, group2, usevar='pooled')
        # statsmodels ttest_ind returns a tuple: (statistic, pvalue, degrees_of_freedom)
        return {
            'statistic': statistic,
            'p_value': p_value,
            'degrees_of_freedom': df,
            'test_name': 'Student t-test (independent)'
        }

    def student_paired_test(self, group1, group2):
        """Student's t-test for paired samples."""
        statistic, p_value = stats.ttest_rel(group1, group2)
        return {
            'statistic': statistic,
            'p_value': p_value,
            'test_name': 'Student t-test (paired)'
        }

    def anova_test(self, *groups):
        """ANOVA test using scipy.stats."""
        # Use f_oneway with column arrays directly
        statistic, p_value = f_oneway(*groups)

        return {
            'statistic': statistic,
            'p_value': p_value,
            'test_name': 'ANOVA'
        }

    # Quantitative tests - non-parametric
    def mann_whitney_test(self, group1, group2):
        """Mann-Whitney U test."""
        statistic, p_value = stats.mannwhitneyu(group1, group2, alternative='two-sided')
        return {
            'statistic': statistic,
            'p_value': p_value,
            'test_name': 'Mann-Whitney U'
        }

    def wilcoxon_test(self, group1, group2):
        """Wilcoxon signed-rank test for paired samples."""
        statistic, p_value = stats.wilcoxon(group1, group2, alternative='two-sided')
        return {
            'statistic': statistic,
            'p_value': p_value,
            'test_name': 'Wilcoxon signed-rank'
        }

    def kruskal_wallis_test(self, *groups):
        """Kruskal-Wallis H test."""
        statistic, p_value = stats.kruskal(*groups)
        return {
            'statistic': statistic,
            'p_value': p_value,
            'test_name': 'Kruskal-Wallis'
        }

    def friedman_test(self, *groups):
        """Friedman test for repeated measures."""
        statistic, p_value = stats.friedmanchisquare(*groups)
        return {
            'statistic': statistic,
            'p_value': p_value,
            'test_name': 'Friedman'
        }

    # Post-hoc tests
    def tukey_hsd_test(self, dataframe):
        """Tukey's HSD post-hoc test after ANOVA."""

        # Melt the dataframe to create group and value columns
        melted_df = pd.melt(dataframe, var_name="group", value_name="value").dropna()

        # Use MultiComparison class
        mc = MultiComparison(melted_df["value"], melted_df["group"])
        tukey_result = mc.tukeyhsd(alpha=0.05)

        return {
            'summary': str(tukey_result),
            'pairwise_comparisons': tukey_result.summary().data,
            'test_name': 'Tukey HSD'
        }

    def dunn_test(self, dataframe, column_names):
        """Dunn's post-hoc test after Kruskal-Wallis."""
        try:
            # Create arrays for Dunn test without melting
            all_values = []
            all_groups = []

            for i, col_name in enumerate(column_names):
                col_data = dataframe.iloc[:, i].dropna()
                all_values.extend(col_data.values)
                all_groups.extend([col_name] * len(col_data))

            # Create temporary dataframe for posthoc_dunn
            temp_df = pd.DataFrame({
                'value': all_values,
                'group': all_groups
            })

            dunn_result = posthoc_dunn(temp_df, val_col='value', group_col='group', p_adjust='bonferroni')
            return {
                'pairwise_matrix': dunn_result.to_dict(),
                'test_name': 'Dunn'
            }
        except Exception as e:
            return {
                'error': f'Error running Dunn test: {str(e)}',
                'test_name': 'Dunn (error)'
            }
