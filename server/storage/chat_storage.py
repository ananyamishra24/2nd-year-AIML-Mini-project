from typing import List, Dict, Optional

class ChatStorage:
    def __init__(self):
        self.conversations = {}
        self.messages = {}
        self.conversation_id_counter = 1
        self.message_id_counter = 1

    def get_all_conversations(self) -> List[Dict]:
        return list(self.conversations.values())

    def get_conversation(self, conversation_id: int) -> Optional[Dict]:
        return self.conversations.get(conversation_id)

    def create_conversation(self, title: str) -> Dict:
        conversation_id = self.conversation_id_counter
        self.conversations[conversation_id] = {
            'id': conversation_id,
            'title': title
        }
        self.conversation_id_counter += 1
        return self.conversations[conversation_id]

    def delete_conversation(self, conversation_id: int) -> None:
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]
            self.messages = {k: v for k, v in self.messages.items() if v['conversation_id'] != conversation_id}

    def create_message(self, conversation_id: int, role: str, content: str) -> Dict:
        message_id = self.message_id_counter
        message = {
            'id': message_id,
            'conversation_id': conversation_id,
            'role': role,
            'content': content
        }
        self.messages[message_id] = message
        self.message_id_counter += 1
        return message

    def get_messages_by_conversation(self, conversation_id: int) -> List[Dict]:
        return [msg for msg in self.messages.values() if msg['conversation_id'] == conversation_id]