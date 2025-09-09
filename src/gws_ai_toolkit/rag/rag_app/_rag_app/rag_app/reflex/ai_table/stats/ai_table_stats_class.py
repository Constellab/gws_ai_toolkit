

from typing import List

import pandas as pd
from pandas import DataFrame, api

from .ai_table_stats_tests import AiTableStatsTests


class AiTableStats:

    _dataframe: DataFrame
    _selected_columns: list[str]

    # True if selected columns are independent (e.g., age, height), False if dependent (e.g., sales over months)
    _columns_are_independent: bool

    _tests: AiTableStatsTests
    test_history: List[dict]

    def __init__(self, dataframe: DataFrame,
                 selected_columns: list[str],
                 columns_are_independent: bool = True):
        self._dataframe = dataframe
        self._selected_columns = selected_columns
        self._columns_are_independent = columns_are_independent
        self._tests = AiTableStatsTests()
        self.test_history = []

    def get_filtered_dataframe(self) -> DataFrame:
        """Get dataframe filtered to only selected columns"""
        if not self._selected_columns:
            return self._dataframe

        return self._dataframe[self._selected_columns]

    def columns_are_quantitative(self) -> bool:
        """Check if all selected columns are quantitative (numeric)"""
        filtered_df = self.get_filtered_dataframe()
        return all(api.types.is_numeric_dtype(filtered_df[col]) for col in filtered_df.columns)

    def _record_test(self, test_category, test_name, result):
        """Record a test result in the history."""
        self.test_history.append({
            'category': test_category,
            'test_name': test_name,
            'result': result,
            'columns': self._selected_columns.copy(),
            'columns_are_independent': self._columns_are_independent
        })

    def run_statistical_analysis(self):
        """Run statistical analysis using decision tree logic."""
        if self.columns_are_quantitative():
            self._analyze_quantitative_columns()
        else:
            self._analyze_qualitative_columns()

    def _analyze_qualitative_columns(self):
        """Analyze qualitative columns using decision tree logic."""
        num_columns = len(self._selected_columns)
        filtered_df = self.get_filtered_dataframe()

        if num_columns == 1:
            # Chi2 adjustment test (goodness of fit)
            print("Running: Khi2 adjustment")
            column_data = filtered_df.iloc[:, 0]
            observed_freq = column_data.value_counts().values
            result = self._tests.chi2_adjustment_test(observed_freq)
            self._record_test("qualitative", "Chi2 adjustment", result)
            print(f"Result: {result}")

        elif num_columns == 2:
            if self._columns_are_independent:
                # Chi2 independence test
                print("Running: Khi2 independance")
                contingency_table = pd.crosstab(filtered_df.iloc[:, 0], filtered_df.iloc[:, 1])
                result = self._tests.chi2_independence_test(contingency_table.values)
                self._record_test("qualitative", "Chi2 independence", result)
                print(f"Result: {result}")
            else:
                # McNemar test
                print("Running: Khi2 McNemar")
                contingency_table = pd.crosstab(filtered_df.iloc[:, 0], filtered_df.iloc[:, 1])
                result = self._tests.mcnemar_test(contingency_table.values)
                self._record_test("qualitative", "McNemar", result)
                print(f"Result: {result}")
        else:
            raise ValueError("Error: More than 2 qualitative columns not supported")

    def _analyze_quantitative_columns(self):
        """Analyze quantitative columns using decision tree logic."""
        num_rows = len(self._dataframe)
        num_columns = len(self._selected_columns)
        filtered_df = self.get_filtered_dataframe()

        # Step 1: Normality test
        normality_results = self._test_normality(filtered_df, num_rows)
        all_normal = normality_results['all_normal']
        print(f"Normality results: {all_normal}")

        # Step 2: Homogeneity of variance test
        homogeneity_result = self._test_homogeneity(filtered_df, all_normal)
        is_homogeneous = homogeneity_result['is_homogeneous']
        print(f"Homogeneity results: {is_homogeneous}")

        # Step 3-5: Choose appropriate test based on results
        if is_homogeneous and all_normal:
            # Fourth step
            if num_columns == 2:
                if self._columns_are_independent:
                    print("Running: Student independent")
                    result = self._tests.student_independent_test(
                        filtered_df.iloc[:, 0], filtered_df.iloc[:, 1]
                    )
                    self._record_test("quantitative", "Student independent", result)
                    print(f"Result: {result}")
                else:
                    print("Running: Student paired")
                    result = self._tests.student_paired_test(
                        filtered_df.iloc[:, 0], filtered_df.iloc[:, 1]
                    )
                    self._record_test("quantitative", "Student paired", result)
                    print(f"Result: {result}")
            elif num_columns > 2:
                if self._columns_are_independent:
                    print("Running: ANOVA")
                    # Prepare data for ANOVA (need to reshape for statsmodels)
                    melted_df = pd.melt(filtered_df, var_name='group', value_name='value')
                    result = self._tests.anova_test(melted_df, 'value ~ C(group)')
                    self._record_test("quantitative", "ANOVA", result)
                    print(f"Result: {result}")

                    # Check if ANOVA is significant and run Tukey post-hoc test
                    try:
                        # Extract p-value from ANOVA table (usually in the first row, 'PR(>F)' column)
                        anova_table = result['anova_table']
                        if hasattr(anova_table, 'iloc') and len(anova_table) > 0:
                            # Get the p-value from the first row (main effect)
                            p_value = anova_table.iloc[0]['PR(>F)'] if 'PR(>F)' in anova_table.columns else None
                            if p_value is not None and p_value < 0.05:
                                print("Running post-hoc: Tukey HSD (ANOVA p < 0.05)")
                                tukey_result = self._tests.tukey_hsd_test(melted_df, 'value ~ C(group)')
                                self._record_test("post-hoc", "Tukey HSD", tukey_result)
                                print(f"Tukey Result: {tukey_result}")
                    except Exception as e:
                        print(f"Could not run Tukey post-hoc test: {str(e)}")
                else:
                    raise ValueError("Error: More than 2 non-independent quantitative columns not supported")
        else:
            # Fifth step
            if num_columns == 2:
                if self._columns_are_independent:
                    print("Running: Mann-Whitney")
                    result = self._tests.mann_whitney_test(
                        filtered_df.iloc[:, 0], filtered_df.iloc[:, 1]
                    )
                    self._record_test("quantitative", "Mann-Whitney", result)
                    print(f"Result: {result}")
                else:
                    print("Running: Wilcoxon")
                    result = self._tests.wilcoxon_test(
                        filtered_df.iloc[:, 0], filtered_df.iloc[:, 1]
                    )
                    self._record_test("quantitative", "Wilcoxon", result)
                    print(f"Result: {result}")
            elif num_columns > 2:
                if self._columns_are_independent:
                    print("Running: Kruskal-Wallis")
                    groups = [filtered_df.iloc[:, i] for i in range(num_columns)]
                    result = self._tests.kruskal_wallis_test(*groups)
                    self._record_test("quantitative", "Kruskal-Wallis", result)
                    print(f"Result: {result}")

                    # Check if Kruskal-Wallis is significant and run Dunn post-hoc test
                    if result['p_value'] < 0.05:
                        print("Running post-hoc: Dunn test (Kruskal-Wallis p < 0.05)")
                        # Prepare data for Dunn test (need to reshape similar to ANOVA)
                        melted_df = pd.melt(filtered_df, var_name='group', value_name='value')
                        dunn_result = self._tests.dunn_test(melted_df)
                        self._record_test("post-hoc", "Dunn", dunn_result)
                        print(f"Dunn Result: {dunn_result}")
                else:
                    print("Running: Friedman")
                    groups = [filtered_df.iloc[:, i] for i in range(num_columns)]
                    result = self._tests.friedman_test(*groups)
                    self._record_test("quantitative", "Friedman", result)
                    print(f"Result: {result}")

    def _test_normality(self, filtered_df, num_rows):
        """Test normality of quantitative columns."""
        all_normal = True
        test_results = []

        for col in filtered_df.columns:
            column_data = filtered_df[col].dropna()

            if num_rows < 50:
                print(f"Running normality test on {col}: Shapiro-Wilk (< 50 rows)")
                result = self._tests.shapiro_wilk_test(column_data)
            else:
                print(f"Running normality test on {col}: Kolmogorov-Smirnov (>= 50 rows)")
                result = self._tests.kolmogorov_smirnov_test(column_data)

            self._record_test("normality", f"{result['test_name']} ({col})", result)
            print(f"Normality result for {col}: {result}")
            test_results.append(result)

            # If any column has p_value <= 0.05, consider all columns as not normal
            if result['p_value'] <= 0.05:
                all_normal = False

        return {
            'all_normal': all_normal,
            'test_results': test_results,
            'test_used': 'Shapiro-Wilk' if num_rows < 50 else 'Kolmogorov-Smirnov'
        }

    def _test_homogeneity(self, filtered_df, all_normal):
        """Test homogeneity of variance."""
        groups = [filtered_df[col].dropna() for col in filtered_df.columns]

        if all_normal:
            print("Running homogeneity test: Bartlett (normal data)")
            result = self._tests.bartlett_test(*groups)
        else:
            print("Running homogeneity test: Levene (non-normal data)")
            result = self._tests.levene_test(*groups)

        self._record_test("homogeneity", result['test_name'], result)
        print(f"Homogeneity result: {result}")

        # If p_value > 0.05, variances are homogeneous
        is_homogeneous = result['p_value'] > 0.05

        return {
            'is_homogeneous': is_homogeneous,
            'test_result': result,
            'test_used': 'Bartlett' if all_normal else 'Levene'
        }
