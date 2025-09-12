
from typing import List, Optional, Union

import numpy as np
import pandas as pd
from plotly.graph_objects import Box, Figure, Heatmap, Scatter


class AiTableStatsPlots:
    """Class containing all statistical tests for AI Table Stats analysis."""

    def generate_p_values_heatmap(self, p_values_matrix: pd.DataFrame, title: str) -> Figure:
        """Generate a heatmap for p-values matrix.

        Args:
            p_values_matrix: DataFrame containing p-values with groups as index and columns
            title: Title for the heatmap

        Returns:
            plotly.graph_objects.Figure: Heatmap figure
        """
        # Create text annotations for the heatmap
        text_matrix = []
        for i in range(len(p_values_matrix.index)):
            text_row = []
            for j in range(len(p_values_matrix.columns)):
                p_val = p_values_matrix.iloc[i, j]
                if pd.isna(p_val):
                    text_row.append("-")
                else:
                    try:
                        p_val_float = float(p_val)
                        if p_val_float == 1.0 and i == j:  # Diagonal elements
                            text_row.append("1.00")
                        elif p_val_float < 0.001:
                            text_row.append(f"{p_val_float:.2e}")
                        elif p_val_float < 0.01:
                            text_row.append(f"{p_val_float:.3f}")
                        else:
                            text_row.append(f"{p_val_float:.3f}")
                    except (ValueError, TypeError):
                        text_row.append(str(p_val))
            text_matrix.append(text_row)

        # Create heatmap
        fig = Figure(data=Heatmap(
            z=p_values_matrix.values,
            x=p_values_matrix.columns.tolist(),
            y=p_values_matrix.index.tolist(),
            text=text_matrix,
            texttemplate="%{text}",
            textfont={"size": 10},
            colorscale=[
                [0, "darkred"],      # Very significant (p < 0.001)
                [0.001, "red"],      # Significant (p < 0.01)
                [0.01, "orange"],    # Marginally significant (p < 0.05)
                [0.05, "yellow"],    # Not significant (p < 0.1)
                [0.1, "lightgreen"],  # Not significant (p < 0.5)
                [0.5, "green"],      # Not significant (p < 1.0)
                [1, "darkgreen"]     # Same groups (p = 1.0)
            ],
            colorbar=dict(
                title="P-value",
                titleside="right",
                tickmode="array",
                tickvals=[0, 0.001, 0.01, 0.05, 0.1, 0.5, 1.0],
                ticktext=["0", "0.001", "0.01", "0.05", "0.1", "0.5", "1.0"]
            ),
            hoverongaps=False,
            hovertemplate='<b>%{y} vs %{x}</b><br>P-value: %{z:.4f}<extra></extra>'
        ))

        fig.update_layout(
            title={
                'text': title,
                'x': 0.5,
                'xanchor': 'center'
            },
            xaxis_title="Groups",
            yaxis_title="Groups",
            xaxis=dict(side="bottom"),
            yaxis=dict(autorange="reversed"),  # Reverse y-axis to match typical matrix display
            template="plotly_white",
        )

        return fig

    def generate_scatter_plot(self, x: Union[np.ndarray, pd.Series, List[float]],
                              y: Union[np.ndarray, pd.Series, List[float]],
                              x_name: Optional[str] = None,
                              y_name: Optional[str] = None,
                              correlation_type: str = "correlation") -> Figure:
        """Generate a scatter plot for correlation analysis.

        Args:
            x: X-axis data values
            y: Y-axis data values
            x_name: Optional name for x-axis. If None, uses "X Variable"
            y_name: Optional name for y-axis. If None, uses "Y Variable"
            correlation_type: Type of correlation for title (e.g., "Pearson", "Spearman")

        Returns:
            plotly.graph_objects.Figure: Scatter plot figure
        """
        # Convert to numpy arrays for consistency
        x_data = np.array(x)
        y_data = np.array(y)

        # Set default names if not provided
        if x_name is None:
            x_name = "X Variable"
        if y_name is None:
            y_name = "Y Variable"

        # Create scatter plot
        fig = Figure()

        fig.add_trace(Scatter(
            x=x_data,
            y=y_data,
            mode='markers',
            marker=dict(
                size=8,
                color='blue',
                opacity=0.7,
                line=dict(width=1, color='darkblue')
            ),
            name='Data Points',
            hovertemplate=f'<b>{x_name}</b>: %{{x}}<br><b>{y_name}</b>: %{{y}}<extra></extra>'
        ))

        # Add trend line
        z = np.polyfit(x_data, y_data, 1)
        p = np.poly1d(z)

        fig.add_trace(Scatter(
            x=x_data,
            y=p(x_data),
            mode='lines',
            line=dict(color='red', width=2, dash='dash'),
            name='Trend Line',
            hoverinfo='skip'
        ))

        fig.update_layout(
            title=f"{correlation_type} Correlation Analysis",
            xaxis_title=x_name,
            yaxis_title=y_name,
            showlegend=True,
            template="plotly_white",
        )

        return fig

    def generate_box_plot(self, groups: List[List[Union[float, int]]],
                          group_names: Optional[List[str]] = None) -> Figure:
        """Generate a box plot for multiple groups of data.

        Args:
            groups: List of data groups, where each group is a list of numeric values
            group_names: Optional list of names for each group. If None, groups will be named "Group 1", "Group 2", etc.

        Returns:
            plotly.graph_objects.Figure: Box plot figure
        """
        if not groups:
            raise ValueError("At least one group must be provided")

        if group_names is None:
            group_names = [f"Group {i+1}" for i in range(len(groups))]

        if len(groups) != len(group_names):
            raise ValueError("Number of groups must match number of group names")

        fig = Figure()

        for i, (group_data, group_name) in enumerate(zip(groups, group_names)):
            fig.add_trace(Box(
                y=group_data,
                name=group_name,
                boxpoints='outliers',
                jitter=0.3,
                pointpos=-1.8
            ))

        fig.update_layout(
            title="Box Plot Comparison",
            yaxis_title="Values",
            xaxis_title="Groups",
            showlegend=False,
            template="plotly_white"
        )

        return fig
