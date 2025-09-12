
import json
from typing import Any, Dict, List, Literal, Optional, Union

import pandas as pd
from gws_core import BaseModelDTO
from plotly.graph_objs import Figure
from pydantic import field_validator

AiTableStatsAdditionalTestName = Literal[
    "Student t-test (independent paired wise)",
]


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
    result_texts: List[str]


class HomogeneityTestDetails(BaseTestDetails):
    groups_count: int


class ChiSquaredAdjustmentTestDetails(BaseTestDetails):
    categories: int
    expected_freq: List[float]


class ChiSquaredIndependenceTestDetails(BaseTestDetails):
    degrees_of_freedom: int
    expected_frequencies: List[List[float]]
    raw_data: Optional[List[List[int]]] = None


class McNemarTestDetails(BaseTestDetails):
    pass  # No additional fields needed, table shape removed as requested


class StudentTTestIndependentDetails(BaseTestDetails):
    degrees_of_freedom: float
    sample_sizes: List[int]


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
    sample_sizes: List[int]


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
    pairwise_comparisons: List[List[Any]]
    significant_pairs: List[str]
    raw_data: Optional[Any] = None


class DunnTestDetails(BaseTestDetails):
    pairwise_matrix: Dict[str, Dict[str, float]]
    adjustment_method: str
    significant_comparisons: int
    raw_data: Optional[Any] = None


class BonferroniTestDetails(BaseTestDetails):
    original_p_values: List[float]
    corrected_p_values: List[float]
    adjustment_method: str
    significant_comparisons: int
    total_comparisons: int
    corrected_alpha: float


class ScheffeTestDetails(BaseTestDetails):
    original_p_values: List[float]
    corrected_p_values: List[float]
    adjustment_method: str
    significant_comparisons: int
    total_comparisons: int
    scheffe_multiplier: float
    num_groups: int


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
    CorrelationPairwiseDetails,
]


class AiTableStatsResults(BaseModelDTO):

    test_name: AiTableStatsTestName
    result_text: str
    result_figure: Optional[Figure] = None
    statistic: Optional[float] = None
    p_value: Optional[float] = None
    details: Optional[AiTableStatsDetailsType] = None

    p_value_scientific: Optional[str] = None
    statistic_scientific: Optional[str] = None

    def __init__(self, **data: Any):
        super().__init__(**data)
        if self.p_value is not None:
            self.p_value_scientific = f"{self.p_value:.2e}"
        if self.statistic is not None:
            self.statistic_scientific = f"{self.statistic:.2e}"

    @field_validator('result_figure', mode='before')  # Updated to field_validator with mode='before'
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
            raise ValueError("result_figure must be a dict or JSON string representing a Plotly result_figure")

        return Figure(value)

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            Figure: lambda fig: json.loads(fig.to_json())
        }


class AiTableStatsResultList():

    _results: List[AiTableStatsResults]

    def __init__(self, results: Optional[List[AiTableStatsResults]] = None):
        self._results = results or []

    def add_result(self, result: AiTableStatsResults):
        self._results.append(result)

    def get_last_result(self) -> Optional[AiTableStatsResults]:
        if self._results:
            return self._results[-1]
        return None

    def get_results(self) -> List[AiTableStatsResults]:
        return self._results

    def get_ai_text_summary(self) -> str:
        summaries = []
        for result in self._results:
            summaries.append(f"Test: {result.test_name}\nResult: {result.result_text}\n")
        return "\n".join(summaries)

    def contains_test(self, test_name: AiTableStatsTestName) -> bool:
        return any(result.test_name == test_name for result in self._results)
