
import numpy as np
import pandas as pd
from plotly.graph_objects import Box, Figure, Heatmap, Histogram, Scatter


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
        # Transform p-values using -log10 for better visualization
        # This creates a logarithmic scale where smaller p-values have higher values
        log_p_values = p_values_matrix.copy()
        for i in range(len(p_values_matrix.index)):
            for j in range(len(p_values_matrix.columns)):
                p_val = p_values_matrix.iloc[i, j]
                if pd.notna(p_val) and p_val > 0:
                    # Use -log10(p) transformation, with special handling for very small values
                    if p_val < 1e-10:
                        log_p_values.iloc[i, j] = 10  # Cap at -log10(1e-10) = 10
                    else:
                        log_p_values.iloc[i, j] = -np.log10(p_val)
                else:
                    log_p_values.iloc[i, j] = np.nan

        # Create text annotations for the heatmap (original p-values)
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

        # Create heatmap using transformed values
        fig = Figure(
            data=Heatmap(
                z=log_p_values.values,
                x=p_values_matrix.columns.tolist(),
                y=p_values_matrix.index.tolist(),
                text=text_matrix,
                texttemplate="%{text}",
                textfont={"size": 10},
                colorscale=[
                    [0.0, "darkgreen"],  # p = 1.0 (-log10(1) = 0)
                    [0.25, "lightgreen"],  # p = 0.1 (-log10(0.1) = 1)
                    [0.5, "yellow"],  # p = 0.05 (-log10(0.05) ≈ 1.3)
                    [0.75, "orange"],  # p = 0.01 (-log10(0.01) = 2)
                    [1.0, "darkred"],  # p < 0.001 (-log10(0.001) = 3+)
                ],
                colorbar=dict(
                    title="P-value",
                    titleside="right",
                    tickmode="array",
                    tickvals=[0, 1, 1.3, 2, 3],
                    ticktext=["1.0", "0.1", "0.05", "0.01", "0.001"],
                    tickfont=dict(size=10),
                ),
                hoverongaps=False,
                hovertemplate="<b>%{y} vs %{x}</b><br>P-value: %{text}<extra></extra>",
            )
        )

        fig.update_layout(
            title={"text": title, "x": 0.5, "xanchor": "center"},
            xaxis_title="Groups",
            yaxis_title="Groups",
            xaxis=dict(side="bottom"),
            yaxis=dict(autorange="reversed"),  # Reverse y-axis to match typical matrix display
            template="plotly_white",
        )

        return fig

    def generate_scatter_plot(
        self,
        x: np.ndarray | pd.Series | list[float],
        y: np.ndarray | pd.Series | list[float],
        x_name: str | None = None,
        y_name: str | None = None,
        correlation_type: str = "correlation",
    ) -> Figure:
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

        fig.add_trace(
            Scatter(
                x=x_data,
                y=y_data,
                mode="markers",
                marker=dict(
                    size=8, color="blue", opacity=0.7, line=dict(width=1, color="darkblue")
                ),
                name="Data Points",
                hovertemplate=f"<b>{x_name}</b>: %{{x}}<br><b>{y_name}</b>: %{{y}}<extra></extra>",
            )
        )

        # Add trend line
        z = np.polyfit(x_data, y_data, 1)
        p = np.poly1d(z)

        fig.add_trace(
            Scatter(
                x=x_data,
                y=p(x_data),
                mode="lines",
                line=dict(color="red", width=2, dash="dash"),
                name="Trend Line",
                hoverinfo="skip",
            )
        )

        fig.update_layout(
            title=f"{correlation_type} Correlation Analysis",
            xaxis_title=x_name,
            yaxis_title=y_name,
            showlegend=True,
            template="plotly_white",
        )

        return fig

    def generate_box_plot(
        self, groups: list[list[float | int]], group_names: list[str] | None = None
    ) -> Figure:
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
            group_names = [f"Group {i + 1}" for i in range(len(groups))]

        if len(groups) != len(group_names):
            raise ValueError("Number of groups must match number of group names")

        fig = Figure()

        for i, (group_data, group_name) in enumerate(zip(groups, group_names)):
            fig.add_trace(
                Box(y=group_data, name=group_name, boxpoints="outliers", jitter=0.3, pointpos=-1.8)
            )

        fig.update_layout(
            title="Box Plot Comparison",
            yaxis_title="Values",
            xaxis_title="Groups",
            showlegend=False,
            template="plotly_white",
        )

        return fig

    def generate_histogram(
        self,
        dataframe: pd.DataFrame,
        title: str = "Distribution Histogram",
        bins: int | None = None,
    ) -> Figure:
        """Generate a histogram with multiple series for each dataframe column.

        Args:
            dataframe: DataFrame containing numeric columns to plot
            title: Title for the histogram
            bins: Number of bins for the histogram. If None, uses auto binning

        Returns:
            plotly.graph_objects.Figure: Histogram figure with multiple series
        """
        if dataframe.empty:
            raise ValueError("DataFrame cannot be empty")

        fig = Figure()

        # Define lighter colors for different series
        colors = [
            "lightblue",
            "lightcoral",
            "lightgreen",
            "lightsalmon",
            "plum",
            "sandybrown",
            "lightpink",
            "lightgray",
            "khaki",
            "lightcyan",
        ]

        for i, col in enumerate(dataframe.columns):
            column_data = dataframe[col].dropna()

            if len(column_data) == 0:
                continue

            color = colors[i % len(colors)]

            fig.add_trace(
                Histogram(
                    x=column_data,
                    name=col,
                    nbinsx=bins,
                    opacity=0.6,  # Make bars transparent
                    marker=dict(color=color, line=dict(color="black", width=1)),
                    hovertemplate=f"<b>{col}</b><br>Value: %{{x}}<br>Count: %{{y}}<extra></extra>",
                )
            )

        fig.update_layout(
            title={"text": title, "x": 0.5, "xanchor": "center"},
            xaxis_title="Values",
            yaxis_title="Frequency",
            barmode="overlay",  # Overlay bars so they can be placed at the same position
            showlegend=True,
            template="plotly_white",
            legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02),
        )

        return fig
