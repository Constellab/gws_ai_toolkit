

from typing import List, Optional, cast

import pandas as pd
from gws_core import Logger
from pandas import DataFrame

from .ai_table_stats_base import AiTableStatsBase
from .ai_table_stats_tests import AiTableStatsTests
from .ai_table_stats_tests_pairwise import AiTableStatsTestsPairWise
from .ai_table_stats_type import (AiTableStatsResults,
                                  NormalitySummaryTestDetails,
                                  StudentTTestPairwiseDetails)


class AiTableStats(AiTableStatsBase):
    """
    Statistical analysis class that follows a decision tree approach for selecting appropriate tests.

    For correlation and relationship analysis between two variables, use the separate
    AiTableRelationStats class which specializes in Pearson and Spearman correlation tests.

    DECISION TREE LOGIC:

    1. DATA TYPE CLASSIFICATION:
       - If all columns are quantitative (numeric) → Go to quantitative analysis
       - If columns are qualitative (categorical) → Go to qualitative analysis

    2. QUALITATIVE ANALYSIS:
       - 1 column: Chi² adjustment test (goodness of fit)
       - 2 columns:
         * Independent: Chi² independence test
         * Dependent: McNemar test
       - >2 columns: Not supported (error)

    3. QUANTITATIVE ANALYSIS:
       Step 1: NORMALITY TEST (for each column)
       - If n < 50: Shapiro-Wilk test
       - If n ≥ 50: Kolmogorov-Smirnov test (Lilliefors)
       - Result: all_normal = True if ALL columns have p > 0.05

       Step 2: HOMOGENEITY OF VARIANCE TEST
       - If all_normal = True: Bartlett test
       - If all_normal = False: Levene test
       - Result: is_homogeneous = True if p > 0.05

       Step 3: PARAMETRIC PATH (if is_homogeneous AND all_normal)
       - 2 columns:
         * Independent: Student's t-test (independent)
         * Dependent: Student's t-test (paired)
       - >2 columns:
         * Independent: ANOVA → If significant (p < 0.05): Tukey HSD post-hoc
         * Dependent: Not supported (error)

       Step 4: NON-PARAMETRIC PATH (if NOT is_homogeneous OR NOT all_normal)
       - 2 columns:
         * Independent: Mann-Whitney test
         * Dependent: Wilcoxon signed-rank test
       - >2 columns:
         * Independent: Kruskal-Wallis → If significant (p < 0.05): Dunn post-hoc
         * Dependent: Friedman test → If significant (p < 0.05): Dunn post-hoc

    INDEPENDENCE vs DEPENDENCE:
    - Independent: Different groups/subjects (e.g., treatment A vs treatment B)
    - Dependent: Same subjects measured multiple times (e.g., before vs after treatment)

    ADDITIONAL TESTS:
    Additional tests can be run after the main statistical analysis to provide more detailed insights:

    - Student t-test (independent paired wise): Performs pairwise comparisons between all column pairs
      using Student's t-test. Available after ANOVA has been performed and shows significant results.

      Prerequisites:
      * ANOVA test must have been performed
      * Tukey HSD test must have been performed

      Correction methods applied:
      * Independent columns with <30 columns: Bonferroni correction
      * Independent columns with ≥30 columns: Tukey correction (already applied)
      * Dependent/paired columns: Scheffe correction

      Optional reference column parameter allows testing only between a reference column and all others,
      rather than all possible pairwise combinations.
    """

    # True if selected columns are independent (e.g., age, height), False if dependent (e.g., sales over months)
    _columns_are_independent: bool

    _tests: AiTableStatsTests

    def __init__(self, dataframe: DataFrame,
                 columns_are_independent: bool = True):
        super().__init__(dataframe)
        self._columns_are_independent = columns_are_independent
        self._tests = AiTableStatsTests()

    def run_statistical_analysis(self) -> None:
        """Run statistical analysis using decision tree logic."""
        if self.columns_are_quantitative():
            self._analyze_quantitative_columns()
        else:
            self._analyze_qualitative_columns()

    def _analyze_qualitative_columns(self) -> None:
        """Analyze qualitative columns using decision tree logic."""
        num_columns = len(self._dataframe.columns)

        if num_columns == 1:
            # Chi2 adjustment test (goodness of fit)
            Logger.debug("Running: Khi2 adjustment")
            column_data = self._dataframe.iloc[:, 0]
            observed_freq = column_data.value_counts().values
            result = self._tests.chi2_adjustment_test(observed_freq)
            self._record_test(result)
            Logger.debug(f"Result: {result}")

        elif num_columns == 2:
            if self._columns_are_independent:
                # Chi2 independence test
                Logger.debug("Running: Khi2 independance")
                contingency_table = pd.crosstab(self._dataframe.iloc[:, 0], self._dataframe.iloc[:, 1])
                result = self._tests.chi2_independence_test(contingency_table.values)
                self._record_test(result)
                Logger.debug(f"Result: {result}")
            else:
                # McNemar test
                Logger.debug("Running: Khi2 McNemar")
                contingency_table = pd.crosstab(self._dataframe.iloc[:, 0], self._dataframe.iloc[:, 1])
                result = self._tests.mcnemar_test(contingency_table.values)
                self._record_test(result)
                Logger.debug(f"Result: {result}")
        else:
            raise ValueError("Error: More than 2 qualitative columns not supported")

    def _analyze_quantitative_columns(self) -> None:
        """Analyze quantitative columns using decision tree logic."""
        num_rows = len(self._dataframe)
        num_columns = len(self._dataframe.columns)

        # Step 1: Normality test
        all_normal = self._test_normality(self._dataframe, num_rows)

        # Step 2: Homogeneity of variance test
        is_homogeneous = self._test_homogeneity(self._dataframe, all_normal)

        # Step 3-5: Choose appropriate test based on results
        if is_homogeneous and all_normal:
            # Fourth step
            if num_columns == 2:
                if self._columns_are_independent:
                    Logger.debug("Running: Student independent")
                    result = self._tests.student_independent_test(
                        self._dataframe.iloc[:, 0], self._dataframe.iloc[:, 1],
                        self._dataframe.columns[0], self._dataframe.columns[1]
                    )
                    self._record_test(result)
                    Logger.debug(f"Result: {result}")
                else:
                    Logger.debug("Running: Student paired")
                    result = self._tests.student_paired_test(
                        self._dataframe.iloc[:, 0], self._dataframe.iloc[:, 1],
                        self._dataframe.columns[0], self._dataframe.columns[1]
                    )
                    self._record_test(result)
                    Logger.debug(f"Result: {result}")
            elif num_columns > 2:
                if self._columns_are_independent:
                    Logger.debug("Running: ANOVA")
                    # Pass DataFrame directly to ANOVA
                    result = self._tests.anova_test(self._dataframe)
                    self._record_test(result)
                    Logger.debug(f"Result: {result}")

                    # Check if ANOVA is significant and run Tukey post-hoc test
                    if result.p_value < 0.05:
                        Logger.debug("Running post-hoc: Tukey HSD (ANOVA p < 0.05)")
                        # Use columns directly for Tukey
                        tukey_result = self._tests.tukey_hsd_test(self._dataframe)
                        self._record_test(tukey_result)
                        Logger.debug(f"Tukey Result: {tukey_result}")
                else:
                    raise ValueError("Error: More than 2 non-independent quantitative columns not supported")
        else:
            # Fifth step
            if num_columns == 2:
                if self._columns_are_independent:
                    Logger.debug("Running: Mann-Whitney")
                    result = self._tests.mann_whitney_test(
                        self._dataframe.iloc[:, 0], self._dataframe.iloc[:, 1],
                        self._dataframe.columns[0], self._dataframe.columns[1]
                    )
                    self._record_test(result)
                    Logger.debug(f"Result: {result}")
                else:
                    Logger.debug("Running: Wilcoxon")
                    result = self._tests.wilcoxon_test(
                        self._dataframe.iloc[:, 0], self._dataframe.iloc[:, 1],
                        self._dataframe.columns[0], self._dataframe.columns[1]
                    )
                    self._record_test(result)
                    Logger.debug(f"Result: {result}")
            elif num_columns > 2:
                if self._columns_are_independent:
                    Logger.debug("Running: Kruskal-Wallis")
                    # Pass DataFrame directly to Kruskal-Wallis
                    result = self._tests.kruskal_wallis_test(self._dataframe)
                    self._record_test(result)
                    Logger.debug(f"Result: {result}")

                    # Check if Kruskal-Wallis is significant and run Dunn post-hoc test
                    if result.p_value < 0.05:
                        Logger.debug("Running post-hoc: Dunn test (Kruskal-Wallis p < 0.05)")
                        # Use columns directly for Dunn
                        dunn_result = self._tests.dunn_test(self._dataframe)
                        self._record_test(dunn_result)
                        Logger.debug(f"Dunn Result: {dunn_result}")
                else:
                    Logger.debug("Running: Friedman")
                    # Pass DataFrame directly to Friedman
                    result = self._tests.friedman_test(self._dataframe)
                    self._record_test(result)
                    Logger.debug(f"Result: {result}")

                    # Check if Friedman is significant and run Dunn post-hoc test
                    if result.p_value < 0.05:
                        Logger.debug("Running post-hoc: Dunn test (Friedman p < 0.05)")
                        # Use columns directly for Dunn
                        dunn_result = self._tests.dunn_test(self._dataframe)
                        self._record_test(dunn_result)
                        Logger.debug(f"Dunn Result: {dunn_result}")

    def _test_normality(self, dataframe: DataFrame, num_rows: int) -> bool:
        """Test normality of quantitative columns."""
        all_normal = True
        result_texts: List[str] = []

        for col in dataframe.columns:
            column_data = dataframe[col].dropna()

            if num_rows < 50:
                Logger.debug(f"Running normality test on {col}: Shapiro-Wilk (< 50 rows)")
                result = self._tests.shapiro_wilk_test(column_data)
            else:
                Logger.debug(f"Running normality test on {col}: Kolmogorov-Smirnov (>= 50 rows)")
                result = self._tests.kolmogorov_smirnov_test(column_data)

            Logger.debug(f"Normality result for {col}: {result}")
            result_texts.append(result.result_text)

            # If any column has p_value <= 0.05, consider all columns as not normal
            if result.p_value <= 0.05:
                all_normal = False

        self._record_test(
            AiTableStatsResults(
                test_name="Normality summary",
                result_text="All columns are normal" if all_normal else "At least one column is not normal",
                details=NormalitySummaryTestDetails(
                    all_normal=all_normal,
                    test_used='Shapiro-Wilk' if num_rows < 50 else 'Kolmogorov-Smirnov',
                    result_texts=result_texts
                )
            ))

        return all_normal

    def _test_homogeneity(self, filtered_df: DataFrame, all_normal: bool) -> bool:
        """Test homogeneity of variance."""
        groups = [filtered_df[col].dropna() for col in filtered_df.columns]

        result: AiTableStatsResults
        if all_normal:
            Logger.debug("Running homogeneity test: Bartlett (normal data)")
            result = self._tests.bartlett_test(*groups)
        else:
            Logger.debug("Running homogeneity test: Levene (non-normal data)")
            result = self._tests.levene_test(*groups)

        self._record_test(result)
        Logger.debug(f"Homogeneity result: {result}")

        # If p_value > 0.05, variances are homogeneous
        return result.p_value > 0.05

    def suggested_additional_tests(self) -> Optional[str]:
        """
        Suggest additional tests to perform based on test history.

        Args:
            test_history: List of test names that have been performed

        Returns:
            Suggested test name or None if no suggestion available
        """
        if not self._tests_history:
            return None

        # If ANOVA was done and Student pairwise not done, suggest Student pairwise
        if self.history_contains("ANOVA") and not self.history_contains("Student t-test (independent paired wise)"):
            return "Student t-test (independent paired wise)"

        return None

    def run_student_independent_pairwise(self, reference_column: Optional[str] = None) -> AiTableStatsResults:
        """
        Run Student t-test (independent paired wise) with appropriate corrections.

        Args:
            reference_column: Optional reference column. If provided, comparisons are only made
                            between this column and all other columns. If None, all pairwise
                            combinations are tested.

        Checks prerequisites:
        - ANOVA must have been performed
        - Tukey HSD must have been performed

        Applies corrections based on:
        - If columns_are_independent:
          - If nb of columns < 30: Bonferroni correction
          - If nb of columns >= 30: Tukey correction (already done, so no additional correction)
        - If columns are paired: Scheffe correction

        Returns:
            AiTableStatsResults with the test results

        Raises:
            ValueError: If prerequisites are not met
        """
        # Check prerequisites
        if not self.history_contains("ANOVA"):
            raise ValueError("Error: ANOVA test must be performed before running Student t-test (independent paired wise)")

        if not self.history_contains("Tukey HSD"):
            raise ValueError(
                "Error: Tukey HSD test must be performed before running Student t-test (independent paired wise)")

        # Get the raw pairwise t-test results
        pair_wise_tester = AiTableStatsTestsPairWise()
        raw_result = pair_wise_tester.student_independent_pairwise_test(self._dataframe, reference_column)
        self._record_test(raw_result)

        details: StudentTTestPairwiseDetails = cast(StudentTTestPairwiseDetails, raw_result.details)
        num_columns = len(self._dataframe.columns)

        correction_result: AiTableStatsResults
        # Apply appropriate correction based on conditions
        if self._columns_are_independent:
            if num_columns < 30:
                # Apply Bonferroni correction
                correction_result = self._tests.bonferroni_test(details.pairwise_comparisons_matrix)
            else:
                # Apply Tukey correction
                correction_result = self._tests.tukey_hsd_test(details.pairwise_comparisons_matrix)
        else:
            # Apply Scheffe correction for paired columns
            # Never called for now
            correction_result = self._tests.scheffe_test(details.pairwise_comparisons_matrix, num_columns)

        self._record_test(correction_result)
        return correction_result
