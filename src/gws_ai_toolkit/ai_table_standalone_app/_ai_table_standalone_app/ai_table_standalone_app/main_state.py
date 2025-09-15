import os
import tempfile

import reflex as rx
from gws_core import File
from gws_reflex_main import ReflexMainState

from .ai_table.ai_table_data_state import AiTableDataState


class MainState(ReflexMainState, rx.State):
    """Main state for handling CSV/Excel data upload and management"""

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        """Handle file upload event and load CSV or Excel data from uploaded file."""
        if not files:
            return
        file = files[0]
        data = await file.read()

        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False,
                                         suffix=os.path.splitext(file.name)[1]) as temp_file:
            temp_file.write(data)
            temp_file_path = temp_file.name

        # Set resource in both states
        data_state: AiTableDataState = await self.get_state(AiTableDataState)
        data_state.set_resource(File(temp_file_path))
