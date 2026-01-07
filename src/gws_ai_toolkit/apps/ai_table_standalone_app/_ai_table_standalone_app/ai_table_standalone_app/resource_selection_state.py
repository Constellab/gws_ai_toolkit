"""State for handling resource selection in the home page."""

import reflex as rx
from gws_core import File, ResourceModel, ResourceSearchBuilder, Table
from gws_reflex_main import ResourceSelectState

from .ai_table.ai_table_data_state import (
    AiTableDataState,
)
from .main_state import MainState


class ResourceSelectionState(ResourceSelectState, rx.State):
    """State that extends ResourceSelectState to handle resource selection for the main app.

    This state acts as a bridge between the resource selection dialog and MainState,
    allowing MainState to remain independent from ResourceSelectState.
    """

    async def create_search_builder(self) -> ResourceSearchBuilder:
        search_builder = await super().create_search_builder()

        # Filter to only Table resources
        search_builder.add_resource_types_and_sub_types_filter([Table, File])

        return search_builder

    async def on_resource_selected(self, resource_model: ResourceModel):
        """Handle resource selection from the dialog.

        Overrides ResourceSelectState.select_resource to delegate to MainState.
        """
        # Get MainState and call its handler
        resource = resource_model.get_resource()
        if not isinstance(resource, Table) and not isinstance(resource, File):
            raise Exception("The selected resource is not a Table or File.")

        table_state = await self.get_state(AiTableDataState)
        if isinstance(resource, File):
            if not resource.is_csv_or_excel():
                raise Exception("The selected File resource is not a CSV or Excel file.")
            # Load the file into a table
            table_state.add_file(resource, resource.name, resource_model.id)
        else:
            table_state.add_table(resource)

        main_state_instance = await self.get_state(MainState)
        return await main_state_instance.after_new_table()
