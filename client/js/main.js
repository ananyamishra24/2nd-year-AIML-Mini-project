// This file contains the main JavaScript logic for the client-side application, handling user interactions and initializing the application.

document.addEventListener("DOMContentLoaded", () => {
    const chatForm = document.getElementById("chat-form");
    const chatInput = document.getElementById("chat-input");
    const chatContainer = document.getElementById("chat-container");

    chatForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const message = chatInput.value.trim();
        if (message) {
            addMessageToChat("user", message);
            chatInput.value = "";
            await sendMessageToServer(message);
        }
    });

    function addMessageToChat(role, content) {
        const messageElement = document.createElement("div");
        messageElement.classList.add("message", role);
        messageElement.textContent = content;
        chatContainer.appendChild(messageElement);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    async function sendMessageToServer(message) {
        try {
            const response = await fetch(`/api/conversations/1/messages`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ content: message }),
            });

            if (!response.ok) {
                throw new Error("Network response was not ok");
            }

            const data = await response.json();
            if (data.error) {
                addMessageToChat("assistant", "Error: " + data.error);
            } else {
                addMessageToChat("assistant", data.content);
            }
        } catch (error) {
            console.error("Error sending message:", error);
            addMessageToChat("assistant", "Error sending message. Please try again.");
        }
    }
});