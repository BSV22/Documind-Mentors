from abc import ABC, abstractmethod
import os
from google import genai


class EmbeddingModel(ABC):

    @abstractmethod
    def embed(self, text: str):
        pass


client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))


class GeminiEmbedding(EmbeddingModel):

    def __init__(self,
                 model="models/gemini-embedding-001"):

        self.model = model

    def embed(self, text: str):

        result = client.models.embed_content(
            model=self.model,
            contents=text
        )

        return result.embeddings[0].values