import os
from google import genai

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))


class LLM:

    def __init__(self,
                 model="models/gemini-3.5-flash"):

        self.model = model

    def generate(self,
                 prompt: str) -> str:

        response = client.models.generate_content(
            model=self.model,
            contents=prompt
        )

        return response.text