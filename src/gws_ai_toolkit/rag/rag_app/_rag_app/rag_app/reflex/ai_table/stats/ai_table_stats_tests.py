
from itertools import combinations
from typing import List, Optional, Union

import numpy as np
import pandas as pd
from scikit_posthocs import posthoc_dunn
from scipy import stats
from scipy.stats import f_oneway, pearsonr, spearmanr
from statsmodels.stats.contingency_tables import mcnemar
from statsmodels.stats.diagnostic import lilliefors
from statsmodels.stats.multicomp import MultiComparison
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.weightstats import ttest_ind

from .ai_table_stats_type import (AiTableStatsResults, AnovaTestDetails,
                                  BonferroniTestDetails,
                                  ChiSquaredAdjustmentTestDetails,
                                  ChiSquaredIndependenceTestDetails,
                                  DunnTestDetails, FriedmanTestDetails,
                                  HomogeneityTestDetails, McNemarTestDetails,
                                  MultiGroupNonParametricTestDetails,
                                  NormalityTestDetails,
                                  PairedNonParametricTestDetails,
                                  ScheffeTestDetails,
                                  StudentTTestIndependentDetails,
                                  StudentTTestPairedDetails,
                                  StudentTTestPairwiseDetails,
                                  TukeyHSDTestDetails,
                                  TwoGroupNonParametricTestDetails)


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
            statistic=float(statistic),
            p_value=float(p_value),
            details=NormalityTestDetails(
                sample_size=len(data)
            )
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
            statistic=float(statistic),
            p_value=float(p_value),
            details=NormalityTestDetails(
                sample_size=len(data)
            )
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
            statistic=float(statistic),
            p_value=float(p_value),
            details=HomogeneityTestDetails(
                groups_count=len(groups)
            )
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
            statistic=float(statistic),
            p_value=float(p_value),
            details=HomogeneityTestDetails(
                groups_count=len(groups)
            )
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
            statistic=float(statistic),
            p_value=float(p_value),
            details=ChiSquaredAdjustmentTestDetails(
                categories=len(observed_freq),
                expected_freq=expected_freq.tolist()
            )
        )

    def chi2_independence_test(self, contingency_table: Union[np.ndarray, List[List[int]]]) -> AiTableStatsResults:
        """Chi-squared test of independence."""
        chi2_stat, p_value, dof, expected = stats.chi2_contingency(contingency_table)

        # Generate result text based on p-value
        if p_value < 0.05:
            result_text = "Variables are significantly associated (not independent)."
        else:
            result_text = "Variables appear to be independent."

        return AiTableStatsResults(
            test_name='Chi-squared independence',
            result_text=result_text,
            result_figure=None,
            statistic=float(chi2_stat),
            p_value=float(p_value),
            details=ChiSquaredIndependenceTestDetails(
                degrees_of_freedom=int(dof),
                expected_frequencies=expected.tolist(),
                raw_data=np.array(contingency_table).tolist()
            )
        )

    def mcnemar_test(self, table: Union[np.ndarray, List[List[int]]]) -> AiTableStatsResults:
        """McNemar's test for paired categorical data."""
        result = mcnemar(table, exact=False, correction=True)

        # Generate result text based on p-value
        if result.pvalue < 0.05:
            result_text = "Significant difference between paired categorical responses."
        else:
            result_text = "No significant difference between paired responses."

        return AiTableStatsResults(
            test_name='McNemar',
            result_text=result_text,
            result_figure=None,
            statistic=float(result.statistic),
            p_value=float(result.pvalue),
            details=McNemarTestDetails()
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
            statistic=float(statistic),
            p_value=float(p_value),
            details=StudentTTestIndependentDetails(
                degrees_of_freedom=df,
                sample_sizes=[len(group1), len(group2)]
            )
        )

    def student_paired_test(self, group1: Union[np.ndarray, pd.Series, List[float]],
                            group2: Union[np.ndarray, pd.Series, List[float]]) -> AiTableStatsResults:
        """Student's t-test for paired samples."""
        statistic, p_value = stats.ttest_rel(group1, group2)

        # Generate result text based on p-value
        if p_value < 0.05:
            result_text = "Significant difference between paired measurements."
        else:
            result_text = "No significant difference between paired measurements."

        return AiTableStatsResults(
            test_name='Student t-test (paired)',
            result_text=result_text,
            result_figure=None,
            statistic=float(statistic),
            p_value=float(p_value),
            details=StudentTTestPairedDetails(
                pairs_count=len(group1)
            )
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
            statistic=float(statistic),
            p_value=float(p_value),
            details=AnovaTestDetails(
                groups_count=len(groups),
                total_observations=sum(len(group) for group in groups)
            )
        )

    def _perform_ttest_comparison(self, group1: pd.Series, group2: pd.Series, 
                                  p_value_matrix: pd.DataFrame, col1: str, col2: str,
                                  valid_comparisons: int, significant_count: int,
                                  should_count: bool = True) -> tuple[int, int]:
        """
        Perform t-test comparison between two groups and update matrix.
        
        Args:
            group1: First group data
            group2: Second group data  
            p_value_matrix: Matrix to update with p-values
            col1: First column name
            col2: Second column name
            valid_comparisons: Current count of valid comparisons
            significant_count: Current count of significant comparisons
            should_count: Whether to count this comparison in statistics
            
        Returns:
            Tuple of (updated valid_comparisons, updated significant_count)
        """
        group1_clean = group1.dropna()
        group2_clean = group2.dropna()

        if len(group1_clean) > 0 and len(group2_clean) > 0:
            statistic, p_value, df = ttest_ind(group1_clean, group2_clean, usevar='pooled')
            p_value_matrix.loc[col1, col2] = float(p_value)
            
            if should_count:
                valid_comparisons += 1
                if p_value < 0.05:
                    significant_count += 1
        else:
            # Set to None for invalid comparisons
            p_value_matrix.loc[col1, col2] = None
                
        return valid_comparisons, significant_count

    def student_independent_pairwise_test(self, dataframe: pd.DataFrame, reference_column: Optional[str] = None) -> AiTableStatsResults:
        """Student's t-test for independent pairwise comparisons (post-hoc after ANOVA).
        
        Args:
            dataframe: DataFrame containing the data
            reference_column: Optional reference column. If provided, comparisons are only made 
                            between this column and all other columns. If None, all pairwise 
                            combinations are tested.
        """
        # Get all columns
        columns = dataframe.columns.tolist()

        if len(columns) < 2:
            raise ValueError("The table must contain at least two columns for pairwise comparisons.")

        if reference_column and reference_column not in columns:
            raise ValueError(f"Reference column '{reference_column}' not found in dataframe columns.")

        # Initialize matrices for p-values and statistics
        p_value_matrix = pd.DataFrame(index=columns, columns=columns, dtype=object)

        # Set diagonal to 0 (comparison of column with itself)
        for col in columns:
            p_value_matrix.loc[col, col] = 0.0

        # Perform pairwise comparisons
        valid_comparisons = 0
        significant_count = 0

        if reference_column:
            # Only compare reference column with all other columns
            for col in columns:
                if col != reference_column:
                    # Compare reference to other column
                    valid_comparisons, significant_count = self._perform_ttest_comparison(
                        dataframe[reference_column], dataframe[col],
                        p_value_matrix, reference_column, col,
                        valid_comparisons, significant_count,
                        should_count=True
                    )
                    # Also set the symmetric entry in the matrix
                    p_value_matrix.loc[col, reference_column] = p_value_matrix.loc[reference_column, col]

            # Set all non-reference comparisons to None
            for i, col1 in enumerate(columns):
                for j, col2 in enumerate(columns):
                    if col1 != reference_column and col2 != reference_column and i != j:
                        p_value_matrix.loc[col1, col2] = None
        else:
            # Original behavior: all pairwise combinations
            for i, col1 in enumerate(columns):
                for j, col2 in enumerate(columns):
                    if i != j:  # Skip diagonal
                        # Only count each pair once for statistics
                        should_count = i < j
                        valid_comparisons, significant_count = self._perform_ttest_comparison(
                            dataframe[col1], dataframe[col2],
                            p_value_matrix, col1, col2,
                            valid_comparisons, significant_count,
                            should_count=should_count
                        )

        if valid_comparisons == 0:
            raise ValueError("No valid pairs with data found for t-tests.")

        # Create combined matrix with p-values as the main result
        if reference_column:
            # When reference column is provided, return only the reference column data
            comparison_matrix = p_value_matrix[[reference_column]]
        else:
            comparison_matrix = p_value_matrix

        if significant_count > 0:
            result_text = f"Significant differences found in {significant_count} of {valid_comparisons} pairwise comparisons."
        else:
            result_text = "No significant pairwise differences found."

        return AiTableStatsResults(
            test_name='Student t-test (independent paired wise)',
            result_text=result_text,
            result_figure=None,
            statistic=None,
            p_value=None,
            details=StudentTTestPairwiseDetails(
                pairwise_comparisons_matrix=comparison_matrix,
                significant_comparisons=significant_count,
                total_comparisons=valid_comparisons
            )
        )

    # Quantitative tests - non-parametric
    def mann_whitney_test(self, group1: Union[np.ndarray, pd.Series, List[float]],
                          group2: Union[np.ndarray, pd.Series, List[float]]) -> AiTableStatsResults:
        """Mann-Whitney test."""
        statistic, p_value = stats.mannwhitneyu(group1, group2, alternative='two-sided')

        # Generate result text based on p-value
        if p_value < 0.05:
            result_text = "Significant difference between group distributions."
        else:
            result_text = "No significant difference between group distributions."

        return AiTableStatsResults(
            test_name='Mann-Whitney',
            result_text=result_text,
            result_figure=None,
            statistic=float(statistic),
            p_value=float(p_value),
            details=TwoGroupNonParametricTestDetails(
                sample_sizes=[len(group1), len(group2)]
            )
        )

    def wilcoxon_test(self, group1: Union[np.ndarray, pd.Series, List[float]],
                      group2: Union[np.ndarray, pd.Series, List[float]]) -> AiTableStatsResults:
        """Wilcoxon signed-rank test for paired samples."""
        statistic, p_value = stats.wilcoxon(group1, group2, alternative='two-sided')

        # Generate result text based on p-value
        if p_value < 0.05:
            result_text = "Significant difference between paired observations."
        else:
            result_text = "No significant difference between paired observations."

        return AiTableStatsResults(
            test_name='Wilcoxon signed-rank',
            result_text=result_text,
            result_figure=None,
            statistic=float(statistic),
            p_value=float(p_value),
            details=PairedNonParametricTestDetails(
                pairs_count=len(group1)
            )
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
            statistic=float(statistic),
            p_value=float(p_value),
            details=MultiGroupNonParametricTestDetails(
                groups_count=len(groups),
                total_observations=sum(len(group) for group in groups)
            )
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
            statistic=float(statistic),
            p_value=float(p_value),
            details=FriedmanTestDetails(
                conditions_count=len(groups),
                subjects_count=len(groups[0]) if groups else 0
            )
        )

    # Correlation tests
    def pearson_correlation_test(self, x: Union[np.ndarray, pd.Series, List[float]],
                                y: Union[np.ndarray, pd.Series, List[float]]) -> AiTableStatsResults:
        """Pearson correlation test between two variables."""
        correlation, p_value = pearsonr(x, y)

        # Generate result text based on p-value and correlation strength
        if p_value < 0.05:
            if abs(correlation) >= 0.7:
                strength = "strong"
            elif abs(correlation) >= 0.3:
                strength = "moderate"
            else:
                strength = "weak"
            
            direction = "positive" if correlation > 0 else "negative"
            result_text = f"Significant {strength} {direction} linear correlation (r={correlation:.3f})."
        else:
            result_text = f"No significant linear correlation (r={correlation:.3f})."

        return AiTableStatsResults(
            test_name='Pearson correlation',
            result_text=result_text,
            result_figure=None,
            statistic=float(correlation),
            p_value=float(p_value),
            details=TwoGroupNonParametricTestDetails(
                sample_sizes=[len(x), len(y)]
            )
        )

    def spearman_correlation_test(self, x: Union[np.ndarray, pd.Series, List[float]],
                                 y: Union[np.ndarray, pd.Series, List[float]]) -> AiTableStatsResults:
        """Spearman rank correlation test between two variables."""
        correlation, p_value = spearmanr(x, y)

        # Generate result text based on p-value and correlation strength
        if p_value < 0.05:
            if abs(correlation) >= 0.7:
                strength = "strong"
            elif abs(correlation) >= 0.3:
                strength = "moderate"
            else:
                strength = "weak"
            
            direction = "positive" if correlation > 0 else "negative"
            result_text = f"Significant {strength} {direction} monotonic correlation (ρ={correlation:.3f})."
        else:
            result_text = f"No significant monotonic correlation (ρ={correlation:.3f})."

        return AiTableStatsResults(
            test_name='Spearman correlation',
            result_text=result_text,
            result_figure=None,
            statistic=float(correlation),
            p_value=float(p_value),
            details=TwoGroupNonParametricTestDetails(
                sample_sizes=[len(x), len(y)]
            )
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
            details=TukeyHSDTestDetails(
                summary=str(tukey_result),
                pairwise_comparisons=tukey_result.summary().data,
                significant_pairs=significant_pairs,
                raw_data=tukey_result
            )
        )

    def dunn_test(self, dataframe: pd.DataFrame) -> AiTableStatsResults:
        """Dunn's post-hoc test after Kruskal-Wallis."""
        # Melt the dataframe to create group and value columns
        melted_df = pd.melt(dataframe, var_name="group", value_name="value").dropna()

        dunn_result = posthoc_dunn(melted_df, val_col='value', group_col='group', p_adjust='bonferroni')

        # Count significant comparisons (p < 0.05)
        significant_count = 0
        for i in dunn_result.index:
            for j in dunn_result.columns:
                if i != j:
                    p_val = dunn_result.loc[i, j]
                    if pd.notna(p_val) and p_val < 0.05:
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
            details=DunnTestDetails(
                pairwise_matrix=dunn_result.to_dict(),
                adjustment_method='bonferroni',
                significant_comparisons=significant_count,
                raw_data=dunn_result
            )
        )

    def bonferroni_test(self, p_values: Union[List[float], pd.DataFrame, pd.Series]) -> AiTableStatsResults:
        """Bonferroni correction for multiple comparisons."""

        # Convert to list if DataFrame or Series
        if isinstance(p_values, pd.DataFrame):
            p_values_list = p_values.values.flatten().tolist()
        elif isinstance(p_values, pd.Series):
            p_values_list = p_values.tolist()
        else:
            p_values_list = p_values

        # Apply Bonferroni correction
        corrected_p_values, _, _, alpha_bonf = multipletests(p_values_list, method='bonferroni')

        # Count significant comparisons after correction
        significant_count = sum(1 for p in corrected_p_values if p < 0.05)

        if significant_count > 0:
            result_text = f"Significant differences found in {significant_count} of {len(p_values_list)} comparisons after Bonferroni correction."
        else:
            result_text = "No significant differences found after Bonferroni correction."

        return AiTableStatsResults(
            test_name='Student t-test (independent paired wise)',
            result_text=result_text,
            result_figure=None,
            statistic=None,
            p_value=None,
            details=BonferroniTestDetails(
                original_p_values=p_values_list,
                corrected_p_values=corrected_p_values.tolist(),
                adjustment_method='bonferroni',
                significant_comparisons=significant_count,
                total_comparisons=len(p_values_list),
                corrected_alpha=float(alpha_bonf)
            )
        )

    def scheffe_test(
            self, p_values: Union[List[float],
                                  pd.DataFrame, pd.Series],
            num_groups: int) -> AiTableStatsResults:
        """Scheffe correction for multiple comparisons."""

        # Convert to list if DataFrame or Series
        if isinstance(p_values, pd.DataFrame):
            p_values_list = p_values.values.flatten().tolist()
        elif isinstance(p_values, pd.Series):
            p_values_list = p_values.tolist()
        else:
            p_values_list = p_values

        if num_groups < 2:
            raise ValueError("Number of groups must be at least 2 for Scheffe correction.")

        # Calculate Scheffe critical value
        critical_value = stats.f.ppf(0.95, num_groups - 1, float('inf'))  # F critical value
        scheffe_multiplier = (num_groups - 1) * critical_value

        # Apply Scheffe correction: multiply p-values by the Scheffe multiplier
        corrected_p_values = [min(1.0, float(p) * float(scheffe_multiplier)) for p in p_values_list]

        # Count significant comparisons after correction
        significant_count = sum(1 for p in corrected_p_values if p < 0.05)

        if significant_count > 0:
            result_text = f"Significant differences found in {significant_count} of {len(p_values_list)} comparisons after Scheffe correction."
        else:
            result_text = "No significant differences found after Scheffe correction."

        return AiTableStatsResults(
            test_name='Student t-test (independent paired wise)',
            result_text=result_text,
            result_figure=None,
            statistic=None,
            p_value=None,
            details=ScheffeTestDetails(
                original_p_values=p_values_list,
                corrected_p_values=corrected_p_values,
                adjustment_method='scheffe',
                significant_comparisons=significant_count,
                total_comparisons=len(p_values_list),
                scheffe_multiplier=float(scheffe_multiplier),
                num_groups=num_groups
            )
        )
