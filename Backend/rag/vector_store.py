import numpy as np
import json
import os


class VectorStore:

    def __init__(self):

        self.vectors = []
        self.texts = []
        self.metadatas = []

    def add(self,
            text,
            embedding,
            metadata=None):

        self.texts.append(text)
        self.vectors.append(np.array(embedding))
        self.metadatas.append(metadata or {})

    def cosine_similarity(self,
                          a,
                          b):

        return np.dot(a, b) / (
            np.linalg.norm(a) *
            np.linalg.norm(b)
        )

    def search(self,
               query_embedding,
               k=3,
               filter_dict=None):

        if not self.vectors:
            return []

        query_embedding = np.array(query_embedding)
        query_norm = np.linalg.norm(query_embedding)
        if query_norm == 0:
            return []

        # Filter indices based on metadata first
        filtered_indices = []
        for i, metadata in enumerate(self.metadatas):
            if filter_dict:
                match = True
                for key, val in filter_dict.items():
                    meta_val = metadata.get(key)
                    if meta_val != val and not (key == "user_id" and meta_val is None):
                        match = False
                        break
                if not match:
                    continue
            filtered_indices.append(i)

        if not filtered_indices:
            return []

        # Perform vectorized cosine similarity computation
        sub_vectors = np.vstack([self.vectors[i] for i in filtered_indices])
        norms = np.linalg.norm(sub_vectors, axis=1)
        norms = np.where(norms == 0, 1.0, norms)

        dot_products = np.dot(sub_vectors, query_embedding)
        similarities = dot_products / (norms * query_norm)

        scores = []
        for sim_idx, orig_idx in enumerate(filtered_indices):
            scores.append((float(similarities[sim_idx]), self.texts[orig_idx]))

        scores.sort(reverse=True, key=lambda x: x[0])
        return scores[:k]

    def delete_document(self, doc_id):
        """Remove all text chunks and vectors associated with a document ID"""
        new_texts = []
        new_vectors = []
        new_metadatas = []
        for text, vector, metadata in zip(self.texts, self.vectors, self.metadatas):
            if metadata.get("doc_id") == doc_id:
                continue
            new_texts.append(text)
            new_vectors.append(vector)
            new_metadatas.append(metadata)
        self.texts = new_texts
        self.vectors = new_vectors
        self.metadatas = new_metadatas

    def save(self, filepath="data/vector_store.json"):
        """Save vectors, texts and metadatas to disk"""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        data = {
            "texts": self.texts,
            "vectors": [v.tolist() for v in self.vectors],
            "metadatas": self.metadatas
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f)
        
        print(f"Vector store saved to {filepath}")

    def load(self, filepath="data/vector_store.json"):
        """Load vectors, texts and metadatas from disk"""
        if not os.path.exists(filepath):
            return False
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        self.texts = data["texts"]
        self.vectors = [np.array(v) for v in data["vectors"]]
        self.metadatas = data.get("metadatas", [{} for _ in range(len(self.texts))])
        
        print(f"Vector store loaded from {filepath}")
        return True