import os
import tempfile
from typing import List

import reflex as rx
from gws_core import File
from gws_reflex_main import ReflexMainState

from .ai_table.ai_table_data_state import AiTableDataState


class MainState(ReflexMainState, rx.State):
    """Main state for handling CSV/Excel data upload and management"""

    @rx.event
    async def handle_upload(self, files: List[rx.UploadFile]):
        """Handle file upload event and load CSV or Excel data from uploaded files."""
        if not files:
            return

        data_state: AiTableDataState = await self.get_state(AiTableDataState)
        tables_before_upload = data_state.count_tables()

        # Process all uploaded files
        for file in files:
            if not file.name:
                continue

            data = await file.read()

            # Save uploaded file to temporary location
            file_extension = os.path.splitext(file.name)[1] if file.name else ".csv"
            with tempfile.NamedTemporaryFile(delete=False,
                                             suffix=file_extension) as temp_file:
                temp_file.write(data)
                temp_file_path = temp_file.name

            # Pass the original filename (without extension) to preserve correct naming
            original_name = os.path.splitext(file.name)[0] if file.name else "untitled"
            data_state.add_file(File(temp_file_path), original_name)

        # If this was the first upload (no tables before), redirect to AI Table page
        if tables_before_upload == 0 and data_state.count_tables() > 0:
            return rx.redirect("/ai-table")
