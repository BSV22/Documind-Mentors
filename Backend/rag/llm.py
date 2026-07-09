import os
from google import genai

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))


class LLM:

    def __init__(self,
                 model="gemini-3-flash-preview"):

        self.model = model

    def generate(self,  
                 prompt: str) -> str:

        response = client.models.generate_content(
            model=self.model,
            contents=prompt
        )

        return response.text