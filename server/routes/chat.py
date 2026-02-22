from flask import Blueprint, request, jsonify
from storage.chat_storage import ChatStorage

chat_bp = Blueprint('chat', __name__)
chat_storage = ChatStorage()

@chat_bp.route('/api/conversations', methods=['GET'])
def get_conversations():
    try:
        conversations = chat_storage.get_all_conversations()
        return jsonify(conversations), 200
    except Exception as e:
        return jsonify({'error': 'Failed to fetch conversations'}), 500

@chat_bp.route('/api/conversations/<int:id>', methods=['GET'])
def get_conversation(id):
    try:
        conversation = chat_storage.get_conversation(id)
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404
        messages = chat_storage.get_messages_by_conversation(id)
        return jsonify({'conversation': conversation, 'messages': messages}), 200
    except Exception as e:
        return jsonify({'error': 'Failed to fetch conversation'}), 500

@chat_bp.route('/api/conversations', methods=['POST'])
def create_conversation():
    try:
        title = request.json.get('title', 'New Chat')
        conversation = chat_storage.create_conversation(title)
        return jsonify(conversation), 201
    except Exception as e:
        return jsonify({'error': 'Failed to create conversation'}), 500

@chat_bp.route('/api/conversations/<int:id>', methods=['DELETE'])
def delete_conversation(id):
    try:
        chat_storage.delete_conversation(id)
        return '', 204
    except Exception as e:
        return jsonify({'error': 'Failed to delete conversation'}), 500

@chat_bp.route('/api/conversations/<int:id>/messages', methods=['POST'])
def send_message(id):
    try:
        content = request.json.get('content')
        chat_storage.create_message(id, 'user', content)
        messages = chat_storage.get_messages_by_conversation(id)
        # Here you would integrate with OpenAI to get a response
        # For now, we will just return a placeholder response
        response_content = "AI response to: " + content
        chat_storage.create_message(id, 'assistant', response_content)
        return jsonify({'content': response_content}), 200
    except Exception as e:
        return jsonify({'error': 'Failed to send message'}), 500