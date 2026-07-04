class PromptBuilder:

    def build(self,
              question,
              contexts):

        context = "\n\n".join(
            text for _, text in contexts
        )

        return f"""
You are a helpful assistant.

Use ONLY the provided context.

Context:
{context}

Question:
{question}

Answer:
"""