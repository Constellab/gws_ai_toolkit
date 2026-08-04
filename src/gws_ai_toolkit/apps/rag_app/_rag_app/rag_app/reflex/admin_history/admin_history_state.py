import reflex as rx
from gws_ai_toolkit.core.utils import Utils
from gws_ai_toolkit.models.chat.chat_conversation import ChatConversation
from gws_ai_toolkit.models.chat.chat_conversation_dto import AdminChatConversationDTO
from gws_ai_toolkit.models.chat.chat_conversation_service import ChatConversationService
from gws_ai_toolkit.models.chat.conversation.ai_expert_chat_conversation import (
    LEGACY_RESOURCE_ID_CONFIG_KEY,
    AiExpertChatConversation,
)
from gws_ai_toolkit.models.chat.conversation.base_chat_conversation import ChatConversationMode
from gws_ai_toolkit.models.chat.message.chat_message_base import ChatMessageBase
from gws_ai_toolkit.models.chat.message.chat_message_types import ChatMessageFront
from gws_ai_toolkit.models.knowledge_base.knowledge_base_service import KnowledgeBaseService
from gws_ai_toolkit.models.user.user import User
from gws_ai_toolkit.rag.common.rag_resource import RagResource
from gws_core import ResourceModel, UserDTO
from gws_reflex_main import ReflexMainState

from ..core.app_config_state import AppConfigState
from ..knowledge_base.core.document_open_action import build_open_document_event_for_id


class AdminHistoryState(rx.State):
    """State for the admin conversation history page.

    Shows all conversations from all users with readonly message viewing.
    The list page is at /admin-history, and clicking a conversation navigates
    to /admin-history/<conversation_id> to view messages.
    Supports server-side filtering by label text, conversation mode, and user.
    """

    conversations: list[AdminChatConversationDTO] = []
    is_loading: bool = False

    # Filters
    filter_label: str = ""
    filter_mode: str = ""
    filter_user_id: str = ""
    users: list[UserDTO] = []

    # Detail page state
    selected_conversation_label: str = ""
    selected_conversation_user: str = ""
    selected_conversation_mode: str = ""
    selected_document_name: str = ""
    # Knowledge-base document of an AI Expert conversation. Empty for a conversation persisted before
    # the embedded knowledge-base stack, which named a lab resource instead — see
    # ``selected_resource_id``.
    selected_document_id: str = ""
    selected_resource_id: str = ""
    detail_messages: list[ChatMessageFront] = []
    is_loading_messages: bool = False

    # Required for ChatConfig compatibility (always inactive)
    is_streaming: bool = False
    current_response_message: ChatMessageFront | None = None

    @rx.var
    async def show_admin_history(self) -> bool:
        """Whether the admin history page should be shown."""
        main_state = await self.get_state(ReflexMainState)
        return await main_state.get_param("show_admin_history", False)

    @rx.event
    async def load_all_conversations(self):
        """Load all conversations and users, applying current filters."""
        self.is_loading = True

        try:
            app_config_state = await AppConfigState.get_instance(self)
            main_state = await self.get_state(ReflexMainState)
            chat_app_name = await app_config_state.get_chat_app_name()

            conversation_service = ChatConversationService()

            with await main_state.authenticate_user():
                conversations = conversation_service.get_all_conversations_by_chat_app(
                    chat_app_name=chat_app_name,
                    label=self.filter_label or None,
                    mode=self.filter_mode or None,
                    user_id=self.filter_user_id or None,
                )
                self.conversations = [conv.to_admin_dto() for conv in conversations]
                self.users = [user.to_dto() for user in User.get_real_users()]
        finally:
            self.is_loading = False

    @rx.event
    async def set_filter_label(self, value: str):
        """Set the label text filter and reload."""
        self.filter_label = value
        await self.load_all_conversations()

    @rx.event
    async def set_filter_mode(self, value: str):
        """Set the mode filter and reload."""
        self.filter_mode = value
        await self.load_all_conversations()

    @rx.event
    async def set_filter_user(self, value: str):
        """Set the user filter and reload."""
        self.filter_user_id = value
        await self.load_all_conversations()

    @rx.event
    async def clear_filters(self):
        """Reset all filters and reload."""
        self.filter_label = ""
        self.filter_mode = ""
        self.filter_user_id = ""
        await self.load_all_conversations()

    @rx.var
    def has_active_filters(self) -> bool:
        """Whether any filter is currently active."""
        return bool(self.filter_label or self.filter_mode or self.filter_user_id)

    @rx.event
    async def load_conversation_from_url(self):
        """Load a conversation from the URL parameter for the detail page."""
        conversation_id = self.conversation_id if hasattr(self, "conversation_id") else None
        if not conversation_id:
            return

        self.is_loading_messages = True
        self.selected_conversation_mode = ""
        self.selected_document_name = ""
        self.selected_document_id = ""
        self.selected_resource_id = ""

        try:
            main_state = await self.get_state(ReflexMainState)
            conversation_service = ChatConversationService()

            with await main_state.authenticate_user():
                # Load conversation metadata for the header
                conversation = ChatConversation.get_by_id_and_check(conversation_id)
                admin_dto = conversation.to_admin_dto()
                self.selected_conversation_label = admin_dto.label
                self.selected_conversation_user = (
                    f"{admin_dto.user_first_name} {admin_dto.user_last_name}"
                )
                self.selected_conversation_mode = admin_dto.mode

                # For AI Expert conversations, resolve the document being discussed
                if admin_dto.mode == ChatConversationMode.AI_EXPERT.value:
                    self._load_ai_expert_document(conversation)

                # Load messages
                messages = conversation_service.get_messages_of_conversation(conversation_id)
                self.detail_messages = [
                    msg.to_front_dto() for msg in ChatMessageBase.filter_visible(messages)
                ]
        finally:
            self.is_loading_messages = False

    def _load_ai_expert_document(self, conversation: ChatConversation) -> None:
        """Name the document an AI Expert conversation was about, whichever stack recorded it.

        Both keys are read because history outlives a migration: a conversation run on the embedded
        knowledge-base stack names a ``document_id``, while one run before it names the
        ``resource_id`` of a lab resource. An admin page whose whole purpose is reading old
        conversations must keep showing the older ones.

        :param conversation: the conversation being opened
        """
        document_id = conversation.configuration.get(
            AiExpertChatConversation.DOCUMENT_ID_CONFIG_KEY
        )
        if document_id:
            document = KnowledgeBaseService().get_document(document_id)
            if document:
                self.selected_document_id = document_id
                self.selected_document_name = document.filename
            return

        resource_id = conversation.configuration.get(LEGACY_RESOURCE_ID_CONFIG_KEY)
        if resource_id:
            resource_model = ResourceModel.get_by_id(resource_id)
            if resource_model:
                self.selected_resource_id = resource_id
                self.selected_document_name = resource_model.name

    @rx.event
    def open_ai_expert(self, rag_document_id: str):
        """Redirect to the AI Expert page for a document.

        :param rag_document_id: The document ID.
        """
        return rx.redirect(f"/ai-expert/{rag_document_id}")

    @rx.event
    async def open_document(self, rag_document_id: str):
        """Redirect the user to an external URL for the document."""
        main_state = await self.get_state(ReflexMainState)
        with await main_state.authenticate_user():
            rag_resource = RagResource.from_document_id(rag_document_id)
            if not rag_resource:
                raise ValueError(f"Resource with ID {rag_document_id} not found")
        return await self.open_document_from_resource(rag_resource.get_id())

    @rx.event
    async def open_document_from_resource(self, resource_id: str):
        """Redirect the user to an external URL for the resource."""
        main_state = await self.get_state(ReflexMainState)
        with await main_state.authenticate_user():
            public_link = Utils.generate_temp_share_resource_link(resource_id)

        if public_link:
            return rx.redirect(public_link, is_external=True)
        return None

    @rx.var
    def can_open_selected_document(self) -> bool:
        """Whether the selected AI Expert conversation's document can still be opened."""
        return bool(self.selected_document_id or self.selected_resource_id)

    @rx.event
    async def open_selected_document(self):
        """Open the document of the currently selected AI Expert conversation."""
        main_state = await self.get_state(ReflexMainState)

        if self.selected_document_id:
            with await main_state.authenticate_user():
                return build_open_document_event_for_id(self.selected_document_id)

        if not self.selected_resource_id:
            return None

        # The legacy path: an AI Expert conversation run against a lab resource.
        with await main_state.authenticate_user():
            public_link = Utils.generate_temp_share_resource_link(self.selected_resource_id)

        if public_link:
            return rx.redirect(public_link, is_external=True)
        return None

    @rx.var
    def chat_messages(self) -> list[ChatMessageBase]:
        """Get detail messages for ChatConfig compatibility."""
        return self.detail_messages

    @rx.var
    def show_empty_chat(self) -> bool:
        """Check if there are no messages in the detail view."""
        return len(self.detail_messages) == 0 and not self.is_loading_messages
