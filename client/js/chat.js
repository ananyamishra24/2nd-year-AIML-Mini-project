// This file contains JavaScript functions related to the chat functionality, including sending messages and updating the chat interface.

const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const chatMessages = document.getElementById('chat-messages');

chatForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const messageContent = chatInput.value.trim();
    if (messageContent) {
        await sendMessage(messageContent);
        chatInput.value = '';
    }
});

async function sendMessage(content) {
    const conversationId = getCurrentConversationId(); // Assume this function retrieves the current conversation ID
    try {
        const response = await fetch(`/api/conversations/${conversationId}/messages`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ content }),
        });

        if (!response.ok) {
            throw new Error('Failed to send message');
        }

        const data = await response.json();
        updateChatInterface(data);
    } catch (error) {
        console.error('Error sending message:', error);
    }
}

function updateChatInterface(data) {
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', 'user-message');
    messageElement.textContent = data.content;
    chatMessages.appendChild(messageElement);
    
    if (data.done) {
        const assistantMessageElement = document.createElement('div');
        assistantMessageElement.classList.add('message', 'assistant-message');
        assistantMessageElement.textContent = 'Assistant: ' + data.content;
        chatMessages.appendChild(assistantMessageElement);
    }
}