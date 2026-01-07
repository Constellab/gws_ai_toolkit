import os
import tempfile

import reflex as rx
from gws_core import File

from .ai_table.ai_table_data_state import AiTableDataState


class MainState(rx.State):
    """Main state for handling CSV/Excel data upload and management"""

    is_uploading: bool = False

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        """Handle file upload event and load CSV or Excel data from uploaded files."""

        try:
            if not files:
                return

            # Process all uploaded files
            for file in files:
                if not file.name:
                    continue

                data = await file.read()

                # Save uploaded file to temporary location
                file_extension = os.path.splitext(file.name)[1] if file.name else ".csv"
                with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
                    temp_file.write(data)
                    temp_file_path = temp_file.name

                # Pass the original filename (without extension) to preserve correct naming
                original_name = os.path.splitext(file.name)[0] if file.name else "untitled"
                data_state: AiTableDataState = await self.get_state(AiTableDataState)
                data_state.add_file(File(temp_file_path), original_name)

            self.is_uploading = False
            await self.after_new_table()
        finally:
            self.is_uploading = False

    @rx.event
    def handle_upload_progress(self, progress: dict):
        if progress["progress"] < 1:
            self.is_uploading = True

    async def after_new_table(
        self,
    ):
        """Handle resource selection from resource select dialog.

        Called by ResourceSelectionState when a resource is selected.
        """
        # If this was the first table
        data_state: AiTableDataState = await self.get_state(AiTableDataState)
        if data_state.count_tables() == 1:
            return rx.redirect("/ai-table")
