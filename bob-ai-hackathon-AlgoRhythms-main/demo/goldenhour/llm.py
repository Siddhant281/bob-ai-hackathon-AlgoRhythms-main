# llm.py
# Placeholder for LLM / AI integration utilities.


def build_prompt(context: str, question: str) -> str:
    """Build a prompt string from context and a user question."""
    return f"Context:\n{context}\n\nQuestion:\n{question}\n\nAnswer:"


def parse_response(raw: str) -> str:
    """Strip and return the model response text."""
    return raw.strip()
