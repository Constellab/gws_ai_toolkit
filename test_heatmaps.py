#!/usr/bin/env python3

import pandas as pd
import numpy as np
from src.gws_ai_toolkit.stats.ai_table_stats_class import AiTableStats

def test_tukey_heatmap():
    """Test Tukey HSD with heatmap generation."""
    print("Testing Tukey HSD with heatmap...")
    
    # Create test data with 3 groups
    np.random.seed(42)
    data = {
        'Group_A': np.random.normal(10, 2, 30),
        'Group_B': np.random.normal(12, 2, 30), 
        'Group_C': np.random.normal(14, 2, 30)
    }
    
    df = pd.DataFrame(data)
    
    # Create stats analyzer
    stats_analyzer = AiTableStats(df, columns_are_independent=True)
    
    # Run statistical analysis - this should trigger ANOVA and then Tukey
    stats_analyzer.run_statistical_analysis()
    
    # Get results
    results = stats_analyzer.get_all_tests_results()
    
    # Find Tukey test result
    tukey_result = None
    for result in results:
        if result.test_name == 'Tukey HSD':
            tukey_result = result
            break
    
    if tukey_result:
        print("✓ Tukey HSD test completed")
        print(f"  Result: {tukey_result.result_text}")
        if tukey_result.result_figure:
            print("✓ Heatmap generated successfully")
        else:
            print("✗ No heatmap generated")
    else:
        print("✗ Tukey HSD test not found")

def test_dunn_heatmap():
    """Test Dunn test with heatmap generation."""
    print("\nTesting Dunn test with heatmap...")
    
    # Create test data with 3 groups (non-normal to trigger non-parametric path)
    np.random.seed(42)
    data = {
        'Group_A': np.random.exponential(2, 30),  # Non-normal distribution
        'Group_B': np.random.exponential(3, 30),
        'Group_C': np.random.exponential(4, 30)
    }
    
    df = pd.DataFrame(data)
    
    # Create stats analyzer
    stats_analyzer = AiTableStats(df, columns_are_independent=True)
    
    # Run statistical analysis - this should trigger Kruskal-Wallis and then Dunn
    stats_analyzer.run_statistical_analysis()
    
    # Get results
    results = stats_analyzer.get_all_tests_results()
    
    # Find Dunn test result
    dunn_result = None
    for result in results:
        if result.test_name == 'Dunn':
            dunn_result = result
            break
    
    if dunn_result:
        print("✓ Dunn test completed")
        print(f"  Result: {dunn_result.result_text}")
        if dunn_result.result_figure:
            print("✓ Heatmap generated successfully")
        else:
            print("✗ No heatmap generated")
    else:
        print("✗ Dunn test not found")

if __name__ == "__main__":
    test_tukey_heatmap()
    test_dunn_heatmap()
    print("\nTest completed!")