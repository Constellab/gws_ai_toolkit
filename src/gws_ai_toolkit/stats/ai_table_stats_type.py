import json
from typing import Any, Literal, Union

import pandas as pd
from gws_core import BaseModelDTO
from plotly.graph_objs import Figure
from pydantic import field_validator

AiTableStatsAdditionalTestName = Literal["Student t-test (independent paired wise)",]


AiTableStatsTestName = Literal[
    "Shapiro-Wilk",
    "Kolmogorov-Smirnov (Lilliefors)",
    "Normality summary",
    "Bartlett",
    "Levene",
    "Chi-squared adjustment",
    "Chi-squared independence",
    "McNemar",
    "Student t-test (independent)",
    "Student t-test (paired)",
    "Student t-test (independent paired wise)",
    "ANOVA",
    "Mann-Whitney",
    "Wilcoxon signed-rank",
    "Kruskal-Wallis",
    "Friedman",
    "Tukey HSD",
    "Dunn",
    "Pearson correlation",
    "Spearman correlation",
]


# Forward declaration of detail types (will be defined later)
class BaseTestDetails(BaseModelDTO):
    class Config:
        arbitrary_types_allowed = True


# Define specific detail classes first
class NormalityTestDetails(BaseTestDetails):
    sample_size: int


class NormalitySummaryTestDetails(BaseTestDetails):
    all_normal: bool
    test_used: str
    result_texts: list[str]


class HomogeneityTestDetails(BaseTestDetails):
    groups_count: int


class ChiSquaredAdjustmentTestDetails(BaseTestDetails):
    categories: int
    expected_freq: list[float]


class ChiSquaredIndependenceTestDetails(BaseTestDetails):
    degrees_of_freedom: int
    expected_frequencies: list[list[float]]
    raw_data: list[list[int]] | None = None


class McNemarTestDetails(BaseTestDetails):
    pass  # No additional fields needed, table shape removed as requested


class StudentTTestIndependentDetails(BaseTestDetails):
    degrees_of_freedom: float
    sample_sizes: list[int]


class StudentTTestPairedDetails(BaseTestDetails):
    pairs_count: int


class AnovaTestDetails(BaseTestDetails):
    groups_count: int
    total_observations: int


class PairwiseComparisonResult(BaseModelDTO):
    pair: str
    statistic: float
    p_value: float
    df: float


class StudentTTestPairwiseDetails(BaseTestDetails):
    # matrice of p_value for each pair
    pairwise_comparisons_matrix: pd.DataFrame
    significant_comparisons: int
    total_comparisons: int


class TwoGroupNonParametricTestDetails(BaseTestDetails):
    sample_sizes: list[int]


class PairedNonParametricTestDetails(BaseTestDetails):
    pairs_count: int


class MultiGroupNonParametricTestDetails(BaseTestDetails):
    groups_count: int
    total_observations: int


class FriedmanTestDetails(BaseTestDetails):
    conditions_count: int
    subjects_count: int


class TukeyHSDTestDetails(BaseTestDetails):
    summary: str
    pairwise_comparisons: list[list[Any]]
    significant_pairs: list[str]
    raw_data: Any | None = None


class DunnTestDetails(BaseTestDetails):
    pairwise_matrix: dict[str, dict[str, float]]
    adjustment_method: str
    significant_comparisons: int
    raw_data: Any | None = None


class BonferroniTestDetails(BaseTestDetails):
    original_p_values: list[float]
    corrected_p_values: list[float]
    adjustment_method: str
    significant_comparisons: int
    total_comparisons: int
    corrected_alpha: float


class ScheffeTestDetails(BaseTestDetails):
    original_p_values: list[float]
    corrected_p_values: list[float]
    adjustment_method: str
    significant_comparisons: int
    total_comparisons: int
    scheffe_multiplier: float
    num_groups: int


class BenjaminiHochbergTestDetails(BaseTestDetails):
    original_p_values: list[float]
    corrected_p_values: list[float]
    adjustment_method: str
    significant_comparisons: int
    total_comparisons: int
    false_discovery_rate: float


class HolmTestDetails(BaseTestDetails):
    original_p_values: list[float]
    corrected_p_values: list[float]
    adjustment_method: str
    significant_comparisons: int
    total_comparisons: int


class CorrelationPairwiseDetails(BaseTestDetails):
    pairwise_comparisons_matrix: pd.DataFrame
    significant_comparisons: int
    total_comparisons: int


# Union type for all test details
AiTableStatsDetailsType = Union[
    NormalityTestDetails,
    NormalitySummaryTestDetails,
    HomogeneityTestDetails,
    ChiSquaredAdjustmentTestDetails,
    ChiSquaredIndependenceTestDetails,
    McNemarTestDetails,
    StudentTTestIndependentDetails,
    StudentTTestPairedDetails,
    AnovaTestDetails,
    StudentTTestPairwiseDetails,
    TwoGroupNonParametricTestDetails,
    PairedNonParametricTestDetails,
    MultiGroupNonParametricTestDetails,
    FriedmanTestDetails,
    TukeyHSDTestDetails,
    DunnTestDetails,
    BonferroniTestDetails,
    ScheffeTestDetails,
    BenjaminiHochbergTestDetails,
    HolmTestDetails,
    CorrelationPairwiseDetails,
]


class AiTableStatsResults(BaseModelDTO):
    test_name: AiTableStatsTestName
    result_text: str
    result_figure: Figure | None = None
    statistic: float | None = None
    p_value: float | None = None
    details: AiTableStatsDetailsType | None = None

    p_value_scientific: str | None = None
    statistic_scientific: str | None = None

    def __init__(self, **data: Any):
        super().__init__(**data)
        if self.p_value is not None:
            self.p_value_scientific = f"{self.p_value:.2e}"
        if self.statistic is not None:
            self.statistic_scientific = f"{self.statistic:.2e}"

    @field_validator(
        "result_figure", mode="before"
    )  # Updated to field_validator with mode='before'
    @classmethod  # Add classmethod decorator (required in V2)
    def deserialize_result_figure(cls, value):
        if not value:
            return None
        if isinstance(value, Figure):
            return value

        if isinstance(value, str):
            # Convert JSON string to Plotly result_figure
            value = json.loads(value)

        if not isinstance(value, dict):
            raise ValueError(
                "result_figure must be a dict or JSON string representing a Plotly result_figure"
            )

        return Figure(value)

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {Figure: lambda fig: json.loads(fig.to_json())}


class AiTableStatsResultList:
    _results: list[AiTableStatsResults]

    def __init__(self, results: list[AiTableStatsResults] | None = None):
        self._results = results or []

    def add_result(self, result: AiTableStatsResults):
        self._results.append(result)

    def get_last_result(self) -> AiTableStatsResults | None:
        if self._results:
            return self._results[-1]
        return None

    def get_results(self) -> list[AiTableStatsResults]:
        return self._results

    def get_ai_text_summary(self) -> str:
        summaries = []
        for result in self._results:
            summaries.append(f"Test: {result.test_name}\nResult: {result.result_text}\n")
        return "\n".join(summaries)

    def contains_test(self, test_name: AiTableStatsTestName) -> bool:
        return any(result.test_name == test_name for result in self._results)
