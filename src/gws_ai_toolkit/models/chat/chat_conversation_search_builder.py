from gws_core.core.classes.search_builder import SearchBuilder

from gws_ai_toolkit.models.chat.chat_conversation import ChatConversation


class ChatConversationSearchBuilder(SearchBuilder):
    """Search builder for ChatConversation model.

    Supports filtering by chat app, label text, conversation mode, and user.
    """

    def __init__(self) -> None:
        super().__init__(
            ChatConversation,
            default_orders=[ChatConversation.last_modified_at.desc()],
        )

    def add_chat_app_filter(self, chat_app_id: str) -> "ChatConversationSearchBuilder":
        """Filter by chat app ID.

        :param chat_app_id: The chat app ID to filter on.
        :return: Self for chaining.
        """
        self.add_expression(ChatConversation.chat_app == chat_app_id)
        return self

    def add_label_filter(self, label: str) -> "ChatConversationSearchBuilder":
        """Filter by label text (case-insensitive contains).

        :param label: The text to search for in labels.
        :return: Self for chaining.
        """
        self.add_expression(ChatConversation.label.contains(label))
        return self

    def add_mode_filter(self, mode: str) -> "ChatConversationSearchBuilder":
        """Filter by conversation mode.

        :param mode: The mode value to match exactly.
        :return: Self for chaining.
        """
        self.add_expression(ChatConversation.mode == mode)
        return self

    def add_user_filter(self, user_id: str) -> "ChatConversationSearchBuilder":
        """Filter by user ID.

        :param user_id: The user ID to filter on.
        :return: Self for chaining.
        """
        self.add_expression(ChatConversation.user == user_id)
        return self
