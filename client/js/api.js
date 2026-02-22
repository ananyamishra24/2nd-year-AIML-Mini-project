// This file contains functions for making API calls to the server, handling requests and responses for chat-related operations.

const API_BASE_URL = '/api/conversations';

async function fetchConversations() {
    try {
        const response = await fetch(API_BASE_URL);
        if (!response.ok) {
            throw new Error('Failed to fetch conversations');
        }
        return await response.json();
    } catch (error) {
        console.error(error);
        throw error;
    }
}

async function fetchConversation(id) {
    try {
        const response = await fetch(`${API_BASE_URL}/${id}`);
        if (!response.ok) {
            throw new Error('Failed to fetch conversation');
        }
        return await response.json();
    } catch (error) {
        console.error(error);
        throw error;
    }
}

async function createConversation(title) {
    try {
        const response = await fetch(API_BASE_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ title }),
        });
        if (!response.ok) {
            throw new Error('Failed to create conversation');
        }
        return await response.json();
    } catch (error) {
        console.error(error);
        throw error;
    }
}

async function deleteConversation(id) {
    try {
        const response = await fetch(`${API_BASE_URL}/${id}`, {
            method: 'DELETE',
        });
        if (!response.ok) {
            throw new Error('Failed to delete conversation');
        }
    } catch (error) {
        console.error(error);
        throw error;
    }
}

async function sendMessage(conversationId, content) {
    try {
        const response = await fetch(`${API_BASE_URL}/${conversationId}/messages`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ content }),
        });
        if (!response.ok) {
            throw new Error('Failed to send message');
        }
        return await response.json();
    } catch (error) {
        console.error(error);
        throw error;
    }
}