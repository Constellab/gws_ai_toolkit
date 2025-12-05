
import numpy as np
import pandas as pd
from plotly.graph_objects import Figure
from scikit_posthocs import posthoc_dunn
from scipy import stats
from scipy.stats import f_oneway, pearsonr, spearmanr
from statsmodels.stats.contingency_tables import mcnemar
from statsmodels.stats.diagnostic import lilliefors
from statsmodels.stats.multicomp import MultiComparison
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.weightstats import ttest_ind

from .ai_table_stats_plots import AiTableStatsPlots
from .ai_table_stats_type import (
    AiTableStatsResults,
    AnovaTestDetails,
    BenjaminiHochbergTestDetails,
    BonferroniTestDetails,
    ChiSquaredAdjustmentTestDetails,
    ChiSquaredIndependenceTestDetails,
    DunnTestDetails,
    FriedmanTestDetails,
    HolmTestDetails,
    HomogeneityTestDetails,
    McNemarTestDetails,
    MultiGroupNonParametricTestDetails,
    NormalityTestDetails,
    PairedNonParametricTestDetails,
    ScheffeTestDetails,
    StudentTTestIndependentDetails,
    StudentTTestPairedDetails,
    TukeyHSDTestDetails,
    TwoGroupNonParametricTestDetails,
)


class AiTableStatsTests:
    """Class containing all statistical tests for AI Table Stats analysis."""

    plots = AiTableStatsPlots()

    # Normality tests
    def shapiro_wilk_test(
        self, data: np.ndarray | pd.Series | list[float]
    ) -> AiTableStatsResults:
        """Shapiro-Wilk normality test."""
        statistic, p_value = stats.shapiro(data)

        # Generate result text based on p-value
        if p_value < 0.05:
            result_text = "Data significantly deviates from normal distribution."
        else:
            result_text = "Data appears to follow a normal distribution."

        return AiTableStatsResults(
            test_name="Shapiro-Wilk",
            result_text=result_text,
            result_figure=None,
            statistic=float(statistic),
            p_value=float(p_value),
            details=NormalityTestDetails(sample_size=len(data)),
        )

    def kolmogorov_smirnov_test(
        self, data: np.ndarray | pd.Series | list[float]
    ) -> AiTableStatsResults:
        """Kolmogorov-Smirnov normality test using Lilliefors from statsmodels."""
        statistic, p_value = lilliefors(data, dist="norm")

        # Generate result text based on p-value
        if p_value < 0.05:
            result_text = "Data significantly deviates from normal distribution."
        else:
            result_text = "Data appears to follow a normal distribution."

        return AiTableStatsResults(
            test_name="Kolmogorov-Smirnov (Lilliefors)",
            result_text=result_text,
            result_figure=None,
            statistic=float(statistic),
            p_value=float(p_value),
            details=NormalityTestDetails(sample_size=len(data)),
        )

    # Homogeneity tests
    def bartlett_test(
        self, *groups: np.ndarray | pd.Series | list[float]
    ) -> AiTableStatsResults:
        """Bartlett's test for homogeneity of variances."""
        statistic, p_value = stats.bartlett(*groups)

        # Generate result text based on p-value
        if p_value < 0.05:
            result_text = "Groups have significantly different variances."
        else:
            result_text = "Groups have similar variances (homogeneity assumption met)."

        return AiTableStatsResults(
            test_name="Bartlett",
            result_text=result_text,
            result_figure=None,
            statistic=float(statistic),
            p_value=float(p_value),
            details=HomogeneityTestDetails(groups_count=len(groups)),
        )

    def levene_test(
        self, *groups: np.ndarray | pd.Series | list[float]
    ) -> AiTableStatsResults:
        """Levene's test for homogeneity of variances."""
        statistic, p_value = stats.levene(*groups)

        # Generate result text based on p-value
        if p_value < 0.05:
            result_text = "Groups have significantly different variances."
        else:
            result_text = "Groups have similar variances (homogeneity assumption met)."

        return AiTableStatsResults(
            test_name="Levene",
            result_text=result_text,
            result_figure=None,
            statistic=float(statistic),
            p_value=float(p_value),
            details=HomogeneityTestDetails(groups_count=len(groups)),
        )

    # Qualitative tests
    def chi2_adjustment_test(
        self, observed_freq: np.ndarray | list[int]
    ) -> AiTableStatsResults:
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
            test_name="Chi-squared adjustment",
            result_text=result_text,
            result_figure=None,
            statistic=float(statistic),
            p_value=float(p_value),
            details=ChiSquaredAdjustmentTestDetails(
                categories=len(observed_freq), expected_freq=expected_freq.tolist()
            ),
        )

    def chi2_independence_test(
        self, contingency_table: np.ndarray | list[list[int]]
    ) -> AiTableStatsResults:
        """Chi-squared test of independence."""
        chi2_stat, p_value, dof, expected = stats.chi2_contingency(contingency_table)

        # Generate result text based on p-value
        if p_value < 0.05:
            result_text = "Variables are significantly associated (not independent)."
        else:
            result_text = "Variables appear to be independent."

        return AiTableStatsResults(
            test_name="Chi-squared independence",
            result_text=result_text,
            result_figure=None,
            statistic=float(chi2_stat),
            p_value=float(p_value),
            details=ChiSquaredIndependenceTestDetails(
                degrees_of_freedom=int(dof),
                expected_frequencies=expected.tolist(),
                raw_data=np.array(contingency_table).tolist(),
            ),
        )

    def mcnemar_test(self, table: np.ndarray | list[list[int]]) -> AiTableStatsResults:
        """McNemar's test for paired categorical data."""
        result = mcnemar(table, exact=False, correction=True)

        # Generate result text based on p-value
        if result.pvalue < 0.05:
            result_text = "Significant difference between paired categorical responses."
        else:
            result_text = "No significant difference between paired responses."

        return AiTableStatsResults(
            test_name="McNemar",
            result_text=result_text,
            result_figure=None,
            statistic=float(result.statistic),
            p_value=float(result.pvalue),
            details=McNemarTestDetails(),
        )

    # Quantitative tests - parametric
    def student_independent_test(
        self,
        group1: np.ndarray | pd.Series | list[float],
        group2: np.ndarray | pd.Series | list[float],
        group_name_1: str | None = None,
        group_name_2: str | None = None,
    ) -> AiTableStatsResults:
        """Student's t-test for independent samples."""

        statistic, p_value, degrees_of_freedom = ttest_ind(group1, group2, usevar="pooled")

        # Generate result text based on p-value
        if p_value < 0.05:
            result_text = "Significant difference between group means."
        else:
            result_text = "No significant difference between group means."

        # Generate box plot
        group_names = [
            group_name_1 if group_name_1 is not None else "Group 1",
            group_name_2 if group_name_2 is not None else "Group 2",
        ]
        box_plot_figure = self.plots.generate_box_plot([list(group1), list(group2)], group_names)

        return AiTableStatsResults(
            test_name="Student t-test (independent)",
            result_text=result_text,
            result_figure=box_plot_figure,
            statistic=float(statistic),
            p_value=float(p_value),
            details=StudentTTestIndependentDetails(
                degrees_of_freedom=degrees_of_freedom, sample_sizes=[len(group1), len(group2)]
            ),
        )

    def student_paired_test(
        self,
        group1: np.ndarray | pd.Series | list[float],
        group2: np.ndarray | pd.Series | list[float],
        group_name_1: str | None = None,
        group_name_2: str | None = None,
    ) -> AiTableStatsResults:
        """Student's t-test for paired samples."""
        statistic, p_value = stats.ttest_rel(group1, group2)

        # Generate result text based on p-value
        if p_value < 0.05:
            result_text = "Significant difference between paired measurements."
        else:
            result_text = "No significant difference between paired measurements."

        # Generate box plot
        group_names = [
            group_name_1 if group_name_1 is not None else "Before",
            group_name_2 if group_name_2 is not None else "After",
        ]
        box_plot_figure = self.plots.generate_box_plot([list(group1), list(group2)], group_names)

        return AiTableStatsResults(
            test_name="Student t-test (paired)",
            result_text=result_text,
            result_figure=box_plot_figure,
            statistic=float(statistic),
            p_value=float(p_value),
            details=StudentTTestPairedDetails(pairs_count=len(group1)),
        )

    def anova_test(self, dataframe: pd.DataFrame) -> AiTableStatsResults:
        """ANOVA test using scipy.stats."""
        # Extract groups from DataFrame columns
        groups = [dataframe[col].dropna() for col in dataframe.columns]

        # Use f_oneway with column arrays directly
        statistic, p_value = f_oneway(*groups)

        # Generate result text based on p-value
        if p_value < 0.05:
            result_text = "Significant differences found between group means."
        else:
            result_text = "No significant differences between group means."

        # Generate box plot using column names
        group_data = [list(group) for group in groups]
        group_names = list(dataframe.columns)
        box_plot_figure = self.plots.generate_box_plot(group_data, group_names)

        return AiTableStatsResults(
            test_name="ANOVA",
            result_text=result_text,
            result_figure=box_plot_figure,
            statistic=float(statistic),
            p_value=float(p_value),
            details=AnovaTestDetails(
                groups_count=len(groups), total_observations=sum(len(group) for group in groups)
            ),
        )

    # Quantitative tests - non-parametric

    def mann_whitney_test(
        self,
        group1: np.ndarray | pd.Series | list[float],
        group2: np.ndarray | pd.Series | list[float],
        group_name_1: str | None = None,
        group_name_2: str | None = None,
    ) -> AiTableStatsResults:
        """Mann-Whitney test."""
        statistic, p_value = stats.mannwhitneyu(group1, group2, alternative="two-sided")

        # Generate result text based on p-value
        if p_value < 0.05:
            result_text = "Significant difference between group distributions."
        else:
            result_text = "No significant difference between group distributions."

        # Generate box plot
        group_names = [
            group_name_1 if group_name_1 is not None else "Group 1",
            group_name_2 if group_name_2 is not None else "Group 2",
        ]
        box_plot_figure = self.plots.generate_box_plot([list(group1), list(group2)], group_names)

        return AiTableStatsResults(
            test_name="Mann-Whitney",
            result_text=result_text,
            result_figure=box_plot_figure,
            statistic=float(statistic),
            p_value=float(p_value),
            details=TwoGroupNonParametricTestDetails(sample_sizes=[len(group1), len(group2)]),
        )

    def wilcoxon_test(
        self,
        group1: np.ndarray | pd.Series | list[float],
        group2: np.ndarray | pd.Series | list[float],
        group_name_1: str | None = None,
        group_name_2: str | None = None,
    ) -> AiTableStatsResults:
        """Wilcoxon signed-rank test for paired samples."""
        statistic, p_value = stats.wilcoxon(group1, group2, alternative="two-sided")

        # Generate result text based on p-value
        if p_value < 0.05:
            result_text = "Significant difference between paired observations."
        else:
            result_text = "No significant difference between paired observations."

        # Generate box plot
        group_names = [
            group_name_1 if group_name_1 is not None else "Before",
            group_name_2 if group_name_2 is not None else "After",
        ]
        box_plot_figure = self.plots.generate_box_plot([list(group1), list(group2)], group_names)

        return AiTableStatsResults(
            test_name="Wilcoxon signed-rank",
            result_text=result_text,
            result_figure=box_plot_figure,
            statistic=float(statistic),
            p_value=float(p_value),
            details=PairedNonParametricTestDetails(pairs_count=len(group1)),
        )

    def kruskal_wallis_test(self, dataframe: pd.DataFrame) -> AiTableStatsResults:
        """Kruskal-Wallis H test."""
        # Extract groups from DataFrame columns
        groups = [dataframe[col].dropna() for col in dataframe.columns]

        statistic, p_value = stats.kruskal(*groups)

        # Generate result text based on p-value
        if p_value < 0.05:
            result_text = "Significant differences found between group distributions."
        else:
            result_text = "No significant differences between group distributions."

        # Generate box plot using column names
        group_data = [list(group) for group in groups]
        group_names = list(dataframe.columns)
        box_plot_figure = self.plots.generate_box_plot(group_data, group_names)

        return AiTableStatsResults(
            test_name="Kruskal-Wallis",
            result_text=result_text,
            result_figure=box_plot_figure,
            statistic=float(statistic),
            p_value=float(p_value),
            details=MultiGroupNonParametricTestDetails(
                groups_count=len(groups), total_observations=sum(len(group) for group in groups)
            ),
        )

    def friedman_test(self, dataframe: pd.DataFrame) -> AiTableStatsResults:
        """Friedman test for repeated measures."""
        # Extract groups from DataFrame columns
        groups = [dataframe[col] for col in dataframe.columns]

        statistic, p_value = stats.friedmanchisquare(*groups)

        # Generate result text based on p-value
        if p_value < 0.05:
            result_text = "Significant differences found in repeated measures."
        else:
            result_text = "No significant differences in repeated measures."

        # Generate box plot using column names
        group_data = [list(group) for group in groups]
        group_names = list(dataframe.columns)
        box_plot_figure = self.plots.generate_box_plot(group_data, group_names)

        return AiTableStatsResults(
            test_name="Friedman",
            result_text=result_text,
            result_figure=box_plot_figure,
            statistic=float(statistic),
            p_value=float(p_value),
            details=FriedmanTestDetails(
                conditions_count=len(groups), subjects_count=len(groups[0]) if groups else 0
            ),
        )

    # Correlation tests
    def pearson_correlation_test(
        self,
        x: np.ndarray | pd.Series | list[float],
        y: np.ndarray | pd.Series | list[float],
        x_name: str | None = None,
        y_name: str | None = None,
        generate_plot: bool = True,
    ) -> AiTableStatsResults:
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
            result_text = (
                f"Significant {strength} {direction} linear correlation (r={correlation:.3f})."
            )
        else:
            result_text = f"No significant linear correlation (r={correlation:.3f})."

        # Generate scatter plot
        scatter_plot_figure: Figure | None = None
        if generate_plot:
            scatter_plot_figure = self.plots.generate_scatter_plot(x, y, x_name, y_name, "Pearson")

        return AiTableStatsResults(
            test_name="Pearson correlation",
            result_text=result_text,
            result_figure=scatter_plot_figure,
            statistic=float(correlation),
            p_value=float(p_value),
            details=TwoGroupNonParametricTestDetails(sample_sizes=[len(x), len(y)]),
        )

    def spearman_correlation_test(
        self,
        x: np.ndarray | pd.Series | list[float],
        y: np.ndarray | pd.Series | list[float],
        x_name: str | None = None,
        y_name: str | None = None,
        generate_plot: bool = True,
    ) -> AiTableStatsResults:
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
            result_text = (
                f"Significant {strength} {direction} monotonic correlation (ρ={correlation:.3f})."
            )
        else:
            result_text = f"No significant monotonic correlation (ρ={correlation:.3f})."

        # Generate scatter plot
        scatter_plot_figure: Figure | None = None
        if generate_plot:
            scatter_plot_figure = self.plots.generate_scatter_plot(x, y, x_name, y_name, "Spearman")

        return AiTableStatsResults(
            test_name="Spearman correlation",
            result_text=result_text,
            result_figure=scatter_plot_figure,
            statistic=float(correlation),
            p_value=float(p_value),
            details=TwoGroupNonParametricTestDetails(sample_sizes=[len(x), len(y)]),
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
            if row[5] == "True":  # reject column
                significant_pairs.append(f"{row[0]} vs {row[1]}")

        if significant_pairs:
            result_text = (
                f"Significant differences found in {len(significant_pairs)} pairwise comparisons."
            )
        else:
            result_text = "No significant pairwise differences found."

        # Create p-values matrix for heatmap
        groups = dataframe.columns.tolist()
        p_values_matrix = pd.DataFrame(index=groups, columns=groups, dtype=float)

        # Fill diagonal with 1.0 (same groups)
        for group in groups:
            p_values_matrix.loc[group, group] = 1.0

        # Fill matrix with p-values from Tukey results
        for row in tukey_result.summary().data[1:]:  # Skip header
            group1, group2, p_adj = row[0], row[1], float(row[4])
            p_values_matrix.loc[group1, group2] = p_adj
            p_values_matrix.loc[group2, group1] = p_adj  # Symmetric matrix

        # Generate heatmap
        heatmap_figure = self.plots.generate_p_values_heatmap(p_values_matrix, "Tukey HSD P-values")

        return AiTableStatsResults(
            test_name="Tukey HSD",
            result_text=result_text,
            result_figure=heatmap_figure,
            statistic=None,
            p_value=None,
            details=TukeyHSDTestDetails(
                summary=str(tukey_result),
                pairwise_comparisons=tukey_result.summary().data,
                significant_pairs=significant_pairs,
                raw_data=tukey_result,
            ),
        )

    def dunn_test(self, dataframe: pd.DataFrame) -> AiTableStatsResults:
        """Dunn's post-hoc test after Kruskal-Wallis."""
        # Melt the dataframe to create group and value columns
        melted_df = pd.melt(dataframe, var_name="group", value_name="value").dropna()

        dunn_result = posthoc_dunn(
            melted_df, val_col="value", group_col="group", p_adjust="bonferroni"
        )

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
            result_text = (
                f"Significant differences found in {significant_count} pairwise comparisons."
            )
        else:
            result_text = "No significant pairwise differences found."

        # Generate heatmap
        heatmap_figure = self.plots.generate_p_values_heatmap(dunn_result, "Dunn Test P-values")

        return AiTableStatsResults(
            test_name="Dunn",
            result_text=result_text,
            result_figure=heatmap_figure,
            statistic=None,
            p_value=None,
            details=DunnTestDetails(
                pairwise_matrix=dunn_result.to_dict(),
                adjustment_method="bonferroni",
                significant_comparisons=significant_count,
                raw_data=dunn_result,
            ),
        )

    def bonferroni_test(self, p_values: pd.DataFrame) -> AiTableStatsResults:
        """Bonferroni correction for multiple comparisons."""

        # Convert DataFrame to list for processing
        p_values_list = p_values.values.flatten().tolist()

        # Apply Bonferroni correction
        rejected, corrected_p_values, _, alpha_bonf = multipletests(
            p_values_list, method="bonferroni"
        )

        # Count significant comparisons after correction
        significant_count = sum(1 for p in corrected_p_values if p < 0.05)

        if significant_count > 0:
            result_text = f"Significant differences found in {significant_count} of {len(p_values_list)} comparisons after Bonferroni correction."
        else:
            result_text = "No significant differences found after Bonferroni correction."

        # Create corrected p-values matrix with same structure as original
        corrected_matrix = p_values.copy()
        corrected_values_reshaped = np.array(corrected_p_values).reshape(p_values.shape)
        corrected_matrix.iloc[:, :] = corrected_values_reshaped
        heatmap_figure = self.plots.generate_p_values_heatmap(
            corrected_matrix, "Bonferroni Corrected P-values"
        )

        return AiTableStatsResults(
            test_name="Student t-test (independent paired wise)",
            result_text=result_text,
            result_figure=heatmap_figure,
            statistic=None,
            p_value=None,
            details=BonferroniTestDetails(
                original_p_values=p_values_list,
                corrected_p_values=corrected_p_values.tolist(),
                adjustment_method="bonferroni",
                significant_comparisons=significant_count,
                total_comparisons=len(p_values_list),
                corrected_alpha=float(alpha_bonf),
            ),
        )

    def scheffe_test(self, p_values: pd.DataFrame, num_groups: int) -> AiTableStatsResults:
        """Scheffe correction for multiple comparisons."""

        # Convert DataFrame to list for processing
        p_values_list = p_values.values.flatten().tolist()

        if num_groups < 2:
            raise ValueError("Number of groups must be at least 2 for Scheffe correction.")

        # Calculate Scheffe critical value
        critical_value = stats.f.ppf(0.95, num_groups - 1, float("inf"))  # F critical value
        scheffe_multiplier = (num_groups - 1) * critical_value

        # Apply Scheffe correction: multiply p-values by the Scheffe multiplier
        corrected_p_values = [min(1.0, float(p) * float(scheffe_multiplier)) for p in p_values_list]

        # Count significant comparisons after correction
        significant_count = sum(1 for p in corrected_p_values if p < 0.05)

        if significant_count > 0:
            result_text = f"Significant differences found in {significant_count} of {len(p_values_list)} comparisons after Scheffe correction."
        else:
            result_text = "No significant differences found after Scheffe correction."

        # Create corrected p-values matrix with same structure as original
        corrected_matrix = p_values.copy()
        corrected_values_reshaped = np.array(corrected_p_values).reshape(p_values.shape)
        corrected_matrix.iloc[:, :] = corrected_values_reshaped
        heatmap_figure = self.plots.generate_p_values_heatmap(
            corrected_matrix, "Scheffé Corrected P-values"
        )

        return AiTableStatsResults(
            test_name="Student t-test (independent paired wise)",
            result_text=result_text,
            result_figure=heatmap_figure,
            statistic=None,
            p_value=None,
            details=ScheffeTestDetails(
                original_p_values=p_values_list,
                corrected_p_values=corrected_p_values,
                adjustment_method="scheffe",
                significant_comparisons=significant_count,
                total_comparisons=len(p_values_list),
                scheffe_multiplier=float(scheffe_multiplier),
                num_groups=num_groups,
            ),
        )

    def benjamini_hochberg_test(
        self, p_values: pd.DataFrame, fdr: float = 0.05
    ) -> AiTableStatsResults:
        """Benjamini-Hochberg correction for controlling false discovery rate (FDR)."""

        # Convert DataFrame to list for processing
        p_values_list = p_values.values.flatten().tolist()

        # Apply Benjamini-Hochberg correction
        _, corrected_p_values, _, _ = multipletests(p_values_list, method="fdr_bh", alpha=fdr)

        # Count significant comparisons after correction
        significant_count = sum(1 for p in corrected_p_values if p < fdr)

        if significant_count > 0:
            result_text = f"Significant differences found in {significant_count} of {len(p_values_list)} comparisons after Benjamini-Hochberg correction (FDR={fdr})."
        else:
            result_text = (
                f"No significant differences found after Benjamini-Hochberg correction (FDR={fdr})."
            )

        # Create corrected p-values matrix with same structure as original
        corrected_matrix = p_values.copy()
        corrected_values_reshaped = np.array(corrected_p_values).reshape(p_values.shape)
        corrected_matrix.iloc[:, :] = corrected_values_reshaped
        heatmap_figure = self.plots.generate_p_values_heatmap(
            corrected_matrix, "Benjamini-Hochberg Corrected P-values"
        )

        return AiTableStatsResults(
            test_name="Student t-test (independent paired wise)",
            result_text=result_text,
            result_figure=heatmap_figure,
            statistic=None,
            p_value=None,
            details=BenjaminiHochbergTestDetails(
                original_p_values=p_values_list,
                corrected_p_values=corrected_p_values.tolist(),
                adjustment_method="fdr_bh",
                significant_comparisons=significant_count,
                total_comparisons=len(p_values_list),
                false_discovery_rate=float(fdr),
            ),
        )

    def holm_test(self, p_values: pd.DataFrame) -> AiTableStatsResults:
        """Holm step-down correction for multiple comparisons."""

        # Convert DataFrame to list for processing
        p_values_list = p_values.values.flatten().tolist()

        # Apply Holm correction
        _, corrected_p_values, _, _ = multipletests(p_values_list, method="holm")

        # Count significant comparisons after correction
        significant_count = sum(1 for p in corrected_p_values if p < 0.05)

        if significant_count > 0:
            result_text = f"Significant differences found in {significant_count} of {len(p_values_list)} comparisons after Holm correction."
        else:
            result_text = "No significant differences found after Holm correction."

        # Create corrected p-values matrix with same structure as original
        corrected_matrix = p_values.copy()
        corrected_values_reshaped = np.array(corrected_p_values).reshape(p_values.shape)
        corrected_matrix.iloc[:, :] = corrected_values_reshaped
        heatmap_figure = self.plots.generate_p_values_heatmap(
            corrected_matrix, "Holm Corrected P-values"
        )

        return AiTableStatsResults(
            test_name="Student t-test (independent paired wise)",
            result_text=result_text,
            result_figure=heatmap_figure,
            statistic=None,
            p_value=None,
            details=HolmTestDetails(
                original_p_values=p_values_list,
                corrected_p_values=corrected_p_values.tolist(),
                adjustment_method="holm",
                significant_comparisons=significant_count,
                total_comparisons=len(p_values_list),
            ),
        )
