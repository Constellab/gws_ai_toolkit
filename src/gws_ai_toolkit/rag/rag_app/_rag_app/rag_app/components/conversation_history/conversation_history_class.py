from typing import List, Optional

from gws_core import BaseModelDTO

from gws_ai_toolkit.rag.rag_app._rag_app.rag_app.components.generic_chat.generic_chat_class import \
    ChatMessage


class ConversationHistory(BaseModelDTO):
    conversation_id: str
    timestamp: str
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
            self._update_label()
    
    def _update_label(self) -> None:
        """Update the label with the first 100 characters of the first user question."""
        for message in self.messages:
            if message.role == "user" and message.content:
                # Take first 100 characters and clean up
                label_text = str(message.content).strip()[:100]
                # Add ellipsis if truncated
                if len(str(message.content).strip()) > 100:
                    label_text += "..."
                self.label = label_text
                break


class ConversationFullHistory(BaseModelDTO):
    conversations: List[ConversationHistory]

    def add_conversation(self, new_conversation: ConversationHistory) -> None:
        """Add or update a conversation in the full history, avoiding duplicates based on conversation_id."""
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
