# Brave Story Maker

Brave Story Maker is a web application that allows users to create and manage chat conversations with an AI assistant. The application consists of a client-side interface built with HTML, CSS, and JavaScript, and a server-side backend implemented in Python.

## Project Structure

```
brave-story-maker
├── client
│   ├── index.html          # Main HTML document for the client-side application
│   ├── css
│   │   ├── main.css        # Main styles for the application
│   │   └── chat.css        # Styles specific to the chat interface
│   └── js
│       ├── main.js         # Main JavaScript logic for the client-side application
│       ├── chat.js         # JavaScript functions related to chat functionality
│       └── api.js          # Functions for making API calls to the server
├── server
│   ├── main.py             # Entry point for the server-side application
│   ├── routes
│   │   └── chat.py         # Routes for handling chat-related requests
│   ├── storage
│   │   └── chat_storage.py  # Handles storage and retrieval of chat data
│   └── integrations
│       └── openai_client.py # Integrates with the OpenAI API
├── requirements.txt        # Python dependencies for the server-side application
└── README.md               # Documentation for the project
```

## Setup Instructions

1. **Clone the repository:**
   ```
   git clone <repository-url>
   cd brave-story-maker
   ```

2. **Install Python dependencies:**
   Make sure you have Python installed, then run:
   ```
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   Create a `.env` file in the server directory and add your OpenAI API key:
   ```
   OPENAI_API_KEY=your_api_key
   OPENAI_BASE_URL=https://api.openai.com/v1
   ```

4. **Run the server:**
   Navigate to the server directory and run:
   ```
   python main.py
   ```

5. **Open the client application:**
   Open `client/index.html` in your web browser to start using the application.

## Usage Guidelines

- Use the chat interface to start a conversation with the AI assistant.
- You can create new conversations, view existing ones, and send messages to the assistant.
- The application stores all conversations and messages, allowing you to revisit them later.

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue for any suggestions or improvements.