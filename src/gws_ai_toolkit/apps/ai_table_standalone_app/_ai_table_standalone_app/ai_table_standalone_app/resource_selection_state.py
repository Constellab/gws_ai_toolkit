"""State for handling resource selection in the home page."""

import reflex as rx
from gws_ai_toolkit.apps.ai_table_standalone_app.analytics_resource_action_plugin import (
    ANALYTICS_APP_RESOURCE_QUERY_PARAM_KEY,
)
from gws_core import File, ResourceModel, ResourceSearchBuilder, Table
from gws_reflex_main import ReflexMainState, ResourceSelectState

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

    @rx.event
    async def load_from_query_param(self):
        """Page load handler for the home page.

        If a ``resource_id`` query param is provided (e.g. ``/?resource_id=ABC``),
        load that Table or Excel/CSV File resource and redirect to the AI Table page.

        On any error (resource not found, wrong type, no access), shows a toast
        and stays on the home page so the user can pick or upload a resource manually.
        """
        main_state = await self.get_state(ReflexMainState)
        query_params = main_state.get_query_params()
        resource_id = query_params.get(ANALYTICS_APP_RESOURCE_QUERY_PARAM_KEY)

        if not resource_id:
            return None

        try:
            table_state = await self.get_state(AiTableDataState)
            # Avoid re-adding the same resource if on_load fires again
            # (e.g. page reload with the query param still in the URL).
            existing = table_state.get_excel_file_by_resource_model_id(resource_id)
            if existing is not None:
                table_state.select_excel_file(existing.id)
            else:
                with await main_state.authenticate_user():
                    table_state.add_resource_model(resource_id)
        except Exception as e:  # noqa: BLE001
            return rx.toast.error(f"Could not load resource: {e}")

        main_state_instance = await self.get_state(MainState)
        return await main_state_instance.after_new_table()
