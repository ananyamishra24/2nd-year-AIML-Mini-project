import openai
import os

class OpenAIClient:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL")
        openai.api_key = self.api_key
        openai.api_base = self.base_url

    def generate_response(self, messages):
        response = openai.ChatCompletion.create(
            model="gpt-5.1",
            messages=messages,
            max_tokens=2048,
            stream=False
        )
        return response.choices[0].message['content'] if response.choices else None