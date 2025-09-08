from typing import Optional

import reflex as rx
from gws_core import File, ResourceModel

from .ai_table_chat_state import AiTableChatState
from .ai_table_data_state import AiTableDataState


class AiTableState(rx.State):
    """Main coordinator state for AI Table functionality.

    This state acts as the main entry point and coordinator between:
    - AiTableDataState: Handles dataframe management and table display
    - AiTableChatState: Handles AI chat functionality

    It provides the main interface for resource loading and validation,
    ensuring both data and chat states are properly initialized.
    """

    # Resource management
    _current_resource_model: Optional[ResourceModel] = None

    async def set_resource(self, resource: ResourceModel):
        """Set the resource to analyze and load it in both data and chat states

        Args:
            resource (ResourceModel): Resource model to set
        """
        if not self.validate_resource(resource):
            print("Invalid resource: not an Excel or CSV file")
            return

        self._current_resource_model = resource

        # Set resource in both states
        data_state: AiTableDataState = await self.get_state(AiTableDataState)
        chat_state: AiTableChatState = await self.get_state(AiTableChatState)

        data_state.set_resource(resource)
        chat_state.set_resource(resource)

    def validate_resource(self, resource: ResourceModel) -> bool:
        """Validate if resource is an Excel or CSV file

        Args:
            resource (ResourceModel): Resource to validate

        Returns:
            bool: True if resource is Excel/CSV, False otherwise
        """
        try:
            file = resource.get_resource()
            if not isinstance(file, File):
                return False
            return file.is_csv_or_excel()
        except Exception:
            return False

    async def load_resource_from_id(self) -> None:
        """Load resource from URL parameter"""
        # Get the dynamic route parameter
        resource_id = self.resource_id if hasattr(self, 'resource_id') else None

        if not resource_id:
            return None

        resource_model = ResourceModel.get_by_id(resource_id)
        if not resource_model:
            raise ValueError(f"Resource with id {resource_id} not found")

        await self.set_resource(resource_model)
