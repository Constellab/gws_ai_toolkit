from unittest import TestCase

import pandas as pd
from gws_core import Table, TaskRunner

from gws_ai_toolkit.tasks.table_subtable_selector import TableSubtableSelector


class TestTableSubtableSelector(TestCase):
    """Unit tests for TableSubtableSelector transformer"""

    def test_basic_row_selection(self):
        """Test basic row selection with all columns"""
        # Create test dataframe
        df = pd.DataFrame({
            'A': [1, 2, 3, 4, 5],
            'B': [10, 20, 30, 40, 50],
            'C': ['a', 'b', 'c', 'd', 'e']
        })
        table = Table(data=df)

        # Select rows 1-3
        runner = TaskRunner(
            task_type=TableSubtableSelector,
            params={
                'start_row': 1,
                'end_row': 3,
                'columns': None,
                'use_first_row_as_header': False
            },
            inputs={TableSubtableSelector.input_name: table}
        )
        outputs = runner.run()
        result = outputs[TableSubtableSelector.output_name]

        # Verify result
        expected_df = df.iloc[1:4]
        self.assertTrue(result.get_data().equals(expected_df))
        self.assertEqual(len(result.get_data()), 3)

    def test_row_and_column_selection(self):
        """Test selection with specific columns"""
        # Create test dataframe
        df = pd.DataFrame({
            'A': [1, 2, 3, 4, 5],
            'B': [10, 20, 30, 40, 50],
            'C': ['a', 'b', 'c', 'd', 'e'],
            'D': [100, 200, 300, 400, 500]
        })
        table = Table(data=df)

        # Select rows 0-2 and columns A and C
        runner = TaskRunner(
            task_type=TableSubtableSelector,
            params={
                'start_row': 0,
                'end_row': 2,
                'columns': ['A', 'C'],
                'use_first_row_as_header': False
            },
            inputs={TableSubtableSelector.input_name: table}
        )
        outputs = runner.run()
        result = outputs[TableSubtableSelector.output_name]

        # Verify result
        expected_df = df.iloc[0:3][['A', 'C']]
        self.assertTrue(result.get_data().equals(expected_df))
        self.assertEqual(len(result.get_data()), 3)
        self.assertEqual(list(result.get_data().columns), ['A', 'C'])

    def test_inverted_row_selection(self):
        """Test that start_row > end_row gets swapped automatically"""
        # Create test dataframe
        df = pd.DataFrame({
            'A': [1, 2, 3, 4, 5],
            'B': [10, 20, 30, 40, 50]
        })
        table = Table(data=df)

        # Select with inverted indices (should be swapped)
        runner = TaskRunner(
            task_type=TableSubtableSelector,
            params={
                'start_row': 3,
                'end_row': 1,
                'columns': None,
                'use_first_row_as_header': False
            },
            inputs={TableSubtableSelector.input_name: table}
        )
        outputs = runner.run()
        result = outputs[TableSubtableSelector.output_name]

        # Verify result (should be rows 1-3)
        expected_df = df.iloc[1:4]
        self.assertTrue(result.get_data().equals(expected_df))

    def test_first_row_as_header(self):
        """Test using first row of selection as header"""
        # Create test dataframe with data that will become headers
        df = pd.DataFrame({
            'A': ['Name', 'Alice', 'Bob', 'Charlie'],
            'B': ['Age', '25', '30', '35'],
            'C': ['City', 'NYC', 'LA', 'SF']
        })
        table = Table(data=df)

        # Select rows 0-3 and use first row as header
        runner = TaskRunner(
            task_type=TableSubtableSelector,
            params={
                'start_row': 0,
                'end_row': 3,
                'columns': None,
                'use_first_row_as_header': True
            },
            inputs={TableSubtableSelector.input_name: table}
        )
        outputs = runner.run()
        result = outputs[TableSubtableSelector.output_name]

        # Verify result
        result_df = result.get_data()
        self.assertEqual(list(result_df.columns), ['Name', 'Age', 'City'])
        self.assertEqual(len(result_df), 3)  # First row used as header, so 3 data rows
        self.assertEqual(result_df.iloc[0]['Name'], 'Alice')

    def test_single_row_selection(self):
        """Test selecting a single row"""
        # Create test dataframe
        df = pd.DataFrame({
            'A': [1, 2, 3, 4, 5],
            'B': [10, 20, 30, 40, 50]
        })
        table = Table(data=df)

        # Select single row (row 2)
        runner = TaskRunner(
            task_type=TableSubtableSelector,
            params={
                'start_row': 2,
                'end_row': 2,
                'columns': None,
                'use_first_row_as_header': False
            },
            inputs={TableSubtableSelector.input_name: table}
        )
        outputs = runner.run()
        result = outputs[TableSubtableSelector.output_name]

        # Verify result
        expected_df = df.iloc[2:3]
        self.assertTrue(result.get_data().equals(expected_df))
        self.assertEqual(len(result.get_data()), 1)

    def test_single_column_selection(self):
        """Test selecting a single column"""
        # Create test dataframe
        df = pd.DataFrame({
            'A': [1, 2, 3, 4, 5],
            'B': [10, 20, 30, 40, 50],
            'C': ['a', 'b', 'c', 'd', 'e']
        })
        table = Table(data=df)

        # Select all rows but only column B
        runner = TaskRunner(
            task_type=TableSubtableSelector,
            params={
                'start_row': 0,
                'end_row': 4,
                'columns': ['B'],
                'use_first_row_as_header': False
            },
            inputs={TableSubtableSelector.input_name: table}
        )
        outputs = runner.run()
        result = outputs[TableSubtableSelector.output_name]

        # Verify result
        expected_df = df[['B']]
        self.assertTrue(result.get_data().equals(expected_df))
        self.assertEqual(result.get_data().columns.tolist(), ['B'])

    def test_out_of_bounds_row_indices(self):
        """Test that out-of-bounds indices are handled gracefully"""
        # Create test dataframe with 5 rows
        df = pd.DataFrame({
            'A': [1, 2, 3, 4, 5],
            'B': [10, 20, 30, 40, 50]
        })
        table = Table(data=df)

        # Try to select beyond table size
        runner = TaskRunner(
            task_type=TableSubtableSelector,
            params={
                'start_row': 2,
                'end_row': 10,  # Beyond table size
                'columns': None,
                'use_first_row_as_header': False
            },
            inputs={TableSubtableSelector.input_name: table}
        )
        outputs = runner.run()
        result = outputs[TableSubtableSelector.output_name]

        # Should clamp to last row (index 4)
        expected_df = df.iloc[2:5]
        self.assertTrue(result.get_data().equals(expected_df))

    def test_invalid_column_names(self):
        """Test handling of invalid column names"""
        # Create test dataframe
        df = pd.DataFrame({
            'A': [1, 2, 3],
            'B': [10, 20, 30]
        })
        table = Table(data=df)

        # Try to select non-existent columns (and one valid)
        runner = TaskRunner(
            task_type=TableSubtableSelector,
            params={
                'start_row': 0,
                'end_row': 2,
                'columns': ['A', 'Z', 'Y'],  # Z and Y don't exist
                'use_first_row_as_header': False
            },
            inputs={TableSubtableSelector.input_name: table}
        )
        outputs = runner.run()
        result = outputs[TableSubtableSelector.output_name]

        # Should only select valid column A
        expected_df = df[['A']]
        self.assertTrue(result.get_data().equals(expected_df))
        self.assertEqual(result.get_data().columns.tolist(), ['A'])

    def test_empty_column_list_selects_all(self):
        """Test that empty column list selects all columns"""
        # Create test dataframe
        df = pd.DataFrame({
            'A': [1, 2, 3],
            'B': [10, 20, 30],
            'C': ['a', 'b', 'c']
        })
        table = Table(data=df)

        # Select with empty column list
        runner = TaskRunner(
            task_type=TableSubtableSelector,
            params={
                'start_row': 0,
                'end_row': 1,
                'columns': [],
                'use_first_row_as_header': False
            },
            inputs={TableSubtableSelector.input_name: table}
        )
        outputs = runner.run()
        result = outputs[TableSubtableSelector.output_name]

        # Should select all columns
        expected_df = df.iloc[0:2]
        self.assertTrue(result.get_data().equals(expected_df))
        self.assertEqual(len(result.get_data().columns), 3)

    def test_full_table_selection(self):
        """Test selecting the entire table"""
        # Create test dataframe
        df = pd.DataFrame({
            'A': [1, 2, 3, 4],
            'B': [10, 20, 30, 40]
        })
        table = Table(data=df)

        # Select entire table
        runner = TaskRunner(
            task_type=TableSubtableSelector,
            params={
                'start_row': 0,
                'end_row': 3,
                'columns': None,
                'use_first_row_as_header': False
            },
            inputs={TableSubtableSelector.input_name: table}
        )
        outputs = runner.run()
        result = outputs[TableSubtableSelector.output_name]

        # Should match original table
        self.assertTrue(result.get_data().equals(df))

    def test_static_method_basic(self):
        """Test the static select_subtable method"""
        # Create test dataframe
        df = pd.DataFrame({
            'A': [1, 2, 3, 4, 5],
            'B': [10, 20, 30, 40, 50],
            'C': ['a', 'b', 'c', 'd', 'e']
        })
        table = Table(data=df)

        # Use static method to select rows 1-3
        result = TableSubtableSelector.select_subtable(
            source_table=table,
            start_row=1,
            end_row=3
        )

        # Verify result
        expected_df = df.iloc[1:4]
        self.assertTrue(result.get_data().equals(expected_df))
        self.assertEqual(len(result.get_data()), 3)

    def test_static_method_with_columns(self):
        """Test the static method with column selection"""
        # Create test dataframe
        df = pd.DataFrame({
            'A': [1, 2, 3, 4],
            'B': [10, 20, 30, 40],
            'C': ['a', 'b', 'c', 'd']
        })
        table = Table(data=df)

        # Use static method with column selection
        result = TableSubtableSelector.select_subtable(
            source_table=table,
            start_row=0,
            end_row=2,
            columns=['A', 'C']
        )

        # Verify result
        expected_df = df.iloc[0:3][['A', 'C']]
        self.assertTrue(result.get_data().equals(expected_df))
        self.assertEqual(list(result.get_data().columns), ['A', 'C'])

    def test_static_method_with_header(self):
        """Test the static method with first row as header"""
        # Create test dataframe
        df = pd.DataFrame({
            'A': ['Name', 'Alice', 'Bob'],
            'B': ['Age', '25', '30'],
            'C': ['City', 'NYC', 'LA']
        })
        table = Table(data=df)

        # Use static method with first row as header
        result = TableSubtableSelector.select_subtable(
            source_table=table,
            start_row=0,
            end_row=2,
            use_first_row_as_header=True
        )

        # Verify result
        result_df = result.get_data()
        self.assertEqual(list(result_df.columns), ['Name', 'Age', 'City'])
        self.assertEqual(len(result_df), 2)
        self.assertEqual(result_df.iloc[0]['Name'], 'Alice')
