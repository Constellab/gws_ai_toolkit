from datetime import datetime
from typing import List, Optional

from gws_core import BaseModelDTO

from ..chat_base.chat_message_class import ChatMessage


class ConversationHistory(BaseModelDTO):
    conversation_id: str
    timestamp: datetime
    configuration: dict
    messages: List[ChatMessage]
    mode: str
    label: str = ""

    def add_messages(self, new_messages: List[ChatMessage]) -> None:
        """Add new messages to the conversation, avoiding duplicates based on message ID."""
        existing_ids = {msg.id for msg in self.messages}

        for message in new_messages:
            if message.id not in existing_ids:
                self.messages.append(message)
                existing_ids.add(message.id)

        # Update label if it's empty and we have a user message
        if not self.label:
            self.update_label()

    def update_label(self) -> None:
        """Update the label with the first 100 characters of the first user question."""
        for message in self.messages:
            if message.role == "user" and message.code:
                # Take first 100 characters and clean up
                label_text = str(message.code).strip()[:100]
                # Add ellipsis if truncated
                if len(str(message.code).strip()) > 100:
                    label_text += "..."
                self.label = label_text
                break

    @classmethod
    def from_json(cls, json_: dict) -> 'ConversationHistory':
        """Create from JSON dict with proper datetime deserialization."""
        # Convert ISO string back to datetime
        if 'timestamp' in json_ and isinstance(json_['timestamp'], str):
            try:
                json_['timestamp'] = datetime.fromisoformat(json_['timestamp'])
            except ValueError:
                # Fallback to current time if parsing fails
                json_['timestamp'] = datetime.now()
        elif 'timestamp' not in json_:
            json_['timestamp'] = datetime.now()

        return super().from_json(json_)


class ConversationFullHistory(BaseModelDTO):
    conversations: List[ConversationHistory]

    def add_conversation(self, new_conversation: ConversationHistory) -> None:
        """Add or update a conversation in the full history, avoiding duplicates based on conversation_id."""
        new_conversation.update_label()  # Ensure label is updated
        # Check if conversation already exists
        conversation = self.get_conversation_by_id(new_conversation.conversation_id)

        if conversation:
            # Update existing conversation - merge messages avoiding duplicates
            conversation.add_messages(new_conversation.messages)
            conversation.timestamp = new_conversation.timestamp  # Update timestamp
            conversation.configuration = new_conversation.configuration  # Update configuration
        else:
            # Add new conversation
            self.conversations.append(new_conversation)

    def get_conversation_by_id(self, conversation_id: str) -> Optional[ConversationHistory]:
        """Get a specific conversation by its ID."""
        for conv in self.conversations:
            if conv.conversation_id == conversation_id:
                return conv
        return None

    def get_all_conversations(self) -> List[ConversationHistory]:
        """Get all conversations as a list."""
        return self.conversations
