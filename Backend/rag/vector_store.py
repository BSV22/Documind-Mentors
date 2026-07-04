import numpy as np
import json
import os


class VectorStore:

    def __init__(self):

        self.vectors = []
        self.texts = []

    def add(self,
            text,
            embedding):

        self.texts.append(text)

        self.vectors.append(np.array(embedding))

    def cosine_similarity(self,
                          a,
                          b):

        return np.dot(a, b) / (
            np.linalg.norm(a) *
            np.linalg.norm(b)
        )

    def search(self,
               query_embedding,
               k=3):

        scores = []

        query_embedding = np.array(query_embedding)

        for text, vector in zip(
                self.texts,
                self.vectors):

            score = self.cosine_similarity(
                query_embedding,
                vector
            )

            scores.append((score, text))

        scores.sort(
            reverse=True,
            key=lambda x: x[0]
        )

        return scores[:k]

    def save(self, filepath="data/vector_store.json"):
        """Save vectors and texts to disk"""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        data = {
            "texts": self.texts,
            "vectors": [v.tolist() for v in self.vectors]
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f)
        
        print(f"Vector store saved to {filepath}")

    def load(self, filepath="data/vector_store.json"):
        """Load vectors and texts from disk"""
        if not os.path.exists(filepath):
            return False
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        self.texts = data["texts"]
        self.vectors = [np.array(v) for v in data["vectors"]]
        
        print(f"Vector store loaded from {filepath}")
        return True