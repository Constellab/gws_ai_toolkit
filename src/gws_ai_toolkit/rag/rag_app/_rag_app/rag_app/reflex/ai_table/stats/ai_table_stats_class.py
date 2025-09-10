

from typing import Any, Dict, List

import pandas as pd
from pandas import DataFrame, api

from .ai_table_stats_tests import AiTableStatsResults, AiTableStatsTests


class AiTableStats:
    """
    Statistical analysis class that follows a decision tree approach for selecting appropriate tests.

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
         * Independent: Mann-Whitney U test
         * Dependent: Wilcoxon signed-rank test
       - >2 columns:
         * Independent: Kruskal-Wallis → If significant (p < 0.05): Dunn post-hoc
         * Dependent: Friedman test

    INDEPENDENCE vs DEPENDENCE:
    - Independent: Different groups/subjects (e.g., treatment A vs treatment B)
    - Dependent: Same subjects measured multiple times (e.g., before vs after treatment)
    """

    _dataframe: DataFrame

    # True if selected columns are independent (e.g., age, height), False if dependent (e.g., sales over months)
    _columns_are_independent: bool

    _tests: AiTableStatsTests
    test_history: List[AiTableStatsResults]

    def __init__(self, dataframe: DataFrame,
                 columns_are_independent: bool = True):
        self._dataframe = dataframe.dropna()
        self._columns_are_independent = columns_are_independent
        self._tests = AiTableStatsTests()
        self.test_history = []

    def columns_are_quantitative(self) -> bool:
        """Check if all columns are quantitative (numeric)"""
        return all(api.types.is_numeric_dtype(self._dataframe[col]) for col in self._dataframe.columns)

    def _record_test(self, result: AiTableStatsResults) -> None:
        """Record a test result in the history."""
        self.test_history.append(result)

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
            print("Running: Khi2 adjustment")
            column_data = self._dataframe.iloc[:, 0]
            observed_freq = column_data.value_counts().values
            result = self._tests.chi2_adjustment_test(observed_freq)
            self._record_test(result)
            print(f"Result: {result}")

        elif num_columns == 2:
            if self._columns_are_independent:
                # Chi2 independence test
                print("Running: Khi2 independance")
                contingency_table = pd.crosstab(self._dataframe.iloc[:, 0], self._dataframe.iloc[:, 1])
                result = self._tests.chi2_independence_test(contingency_table.values)
                self._record_test(result)
                print(f"Result: {result}")
            else:
                # McNemar test
                print("Running: Khi2 McNemar")
                contingency_table = pd.crosstab(self._dataframe.iloc[:, 0], self._dataframe.iloc[:, 1])
                result = self._tests.mcnemar_test(contingency_table.values)
                self._record_test(result)
                print(f"Result: {result}")
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
                    print("Running: Student independent")
                    result = self._tests.student_independent_test(
                        self._dataframe.iloc[:, 0], self._dataframe.iloc[:, 1]
                    )
                    self._record_test(result)
                    print(f"Result: {result}")
                else:
                    print("Running: Student paired")
                    result = self._tests.student_paired_test(
                        self._dataframe.iloc[:, 0], self._dataframe.iloc[:, 1]
                    )
                    self._record_test(result)
                    print(f"Result: {result}")
            elif num_columns > 2:
                if self._columns_are_independent:
                    print("Running: ANOVA")
                    # Use columns directly for ANOVA
                    groups = [self._dataframe.iloc[:, i].dropna() for i in range(num_columns)]
                    result = self._tests.anova_test(*groups)
                    self._record_test(result)
                    print(f"Result: {result}")

                    # Check if ANOVA is significant and run Tukey post-hoc test
                    if result.p_value < 0.05:
                        print("Running post-hoc: Tukey HSD (ANOVA p < 0.05)")
                        # Use columns directly for Tukey
                        tukey_result = self._tests.tukey_hsd_test(self._dataframe)
                        self._record_test(tukey_result)
                        print(f"Tukey Result: {tukey_result}")
                else:
                    raise ValueError("Error: More than 2 non-independent quantitative columns not supported")
        else:
            # Fifth step
            if num_columns == 2:
                if self._columns_are_independent:
                    print("Running: Mann-Whitney")
                    result = self._tests.mann_whitney_test(
                        self._dataframe.iloc[:, 0], self._dataframe.iloc[:, 1]
                    )
                    self._record_test(result)
                    print(f"Result: {result}")
                else:
                    print("Running: Wilcoxon")
                    result = self._tests.wilcoxon_test(
                        self._dataframe.iloc[:, 0], self._dataframe.iloc[:, 1]
                    )
                    self._record_test(result)
                    print(f"Result: {result}")
            elif num_columns > 2:
                if self._columns_are_independent:
                    print("Running: Kruskal-Wallis")
                    groups = [self._dataframe.iloc[:, i].dropna() for i in range(num_columns)]
                    result = self._tests.kruskal_wallis_test(*groups)
                    self._record_test(result)
                    print(f"Result: {result}")

                    # Check if Kruskal-Wallis is significant and run Dunn post-hoc test
                    if result.p_value < 0.05:
                        print("Running post-hoc: Dunn test (Kruskal-Wallis p < 0.05)")
                        # Use columns directly for Dunn
                        dunn_result = self._tests.dunn_test(self._dataframe)
                        self._record_test(dunn_result)
                        print(f"Dunn Result: {dunn_result}")
                else:
                    print("Running: Friedman")
                    groups = [self._dataframe.iloc[:, i] for i in range(num_columns)]
                    result = self._tests.friedman_test(*groups)
                    self._record_test(result)
                    print(f"Result: {result}")

    def _test_normality(self, dataframe: DataFrame, num_rows: int) -> bool:
        """Test normality of quantitative columns."""
        all_normal = True
        test_results = []

        for col in dataframe.columns:
            column_data = dataframe[col].dropna()

            if num_rows < 50:
                print(f"Running normality test on {col}: Shapiro-Wilk (< 50 rows)")
                result = self._tests.shapiro_wilk_test(column_data)
            else:
                print(f"Running normality test on {col}: Kolmogorov-Smirnov (>= 50 rows)")
                result = self._tests.kolmogorov_smirnov_test(column_data)

            print(f"Normality result for {col}: {result}")
            test_results.append(result)

            # If any column has p_value <= 0.05, consider all columns as not normal
            if result.p_value <= 0.05:
                all_normal = False

        self._record_test(
            AiTableStatsResults(
                test_name="Normality Summary",
                result_text="All columns are normal" if all_normal else "At least one column is not normal",
                details={
                    'all_normal': all_normal,
                    'test_used': 'Shapiro-Wilk' if num_rows < 50 else 'Kolmogorov-Smirnov',
                    'individual_results': test_results
                }
            ))

        return all_normal

    def _test_homogeneity(self, filtered_df: DataFrame, all_normal: bool) -> bool:
        """Test homogeneity of variance."""
        groups = [filtered_df[col].dropna() for col in filtered_df.columns]

        if all_normal:
            print("Running homogeneity test: Bartlett (normal data)")
            result = self._tests.bartlett_test(*groups)
        else:
            print("Running homogeneity test: Levene (non-normal data)")
            result = self._tests.levene_test(*groups)

        self._record_test(result)
        print(f"Homogeneity result: {result}")

        # If p_value > 0.05, variances are homogeneous
        return result.p_value > 0.05
