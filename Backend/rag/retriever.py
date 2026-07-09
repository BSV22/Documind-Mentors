class Retriever:

    def __init__(self,
                 embedding_model,
                 vector_store):

        self.embedding_model = embedding_model
        self.vector_store = vector_store

    def retrieve(self,
                 question,
                 user_id=None,
                 top_k=3):

        query_embedding = self.embedding_model.embed(question)

        filter_dict = {"user_id": user_id} if user_id is not None else None

        return self.vector_store.search(
            query_embedding,
            k=top_k,
            filter_dict=filter_dict
        )