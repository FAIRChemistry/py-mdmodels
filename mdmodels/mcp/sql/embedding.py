from __future__ import annotations

from mdmodels.sql.vector import TextEmbedding


def embed_query(embedding_model: TextEmbedding, query: str):
    """Embed a query string with the configured text embedding model.

    This function takes a text query and converts it into a vector embedding
    using the provided embedding model. The resulting embedding can be used
    for semantic similarity searches against database records with stored
    embeddings.

    Args:
        embedding_model: The TextEmbedding instance configured for the database
        query: The text string to be converted into an embedding vector

    Returns:
        The embedding vector representation of the query text, typically as a
        list or array of floating-point numbers
    """
    return embedding_model.embed(query)
