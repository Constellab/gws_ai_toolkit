
from typing import Any, Dict, List, Literal, Optional, Union

import pandas as pd
# import plotly.graph_objs as go
from gws_core import BaseModelDTO

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
]


class AiTableStatsResults(BaseModelDTO):

    test_name: AiTableStatsTestName
    result_text: str
    result_figure: Optional[str] = None
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

    # class Config:
    #     arbitrary_types_allowed = True
