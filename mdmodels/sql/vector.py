"""Lightweight wrappers around multiple text embedding backends."""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Any, Sequence

from pydantic import BaseModel, ConfigDict, field_validator

if TYPE_CHECKING:
    from openai import OpenAI

# Type alias for a single embedding vector represented as a list of floats.
EmbeddingVector = list[float]

# Type alias for a batch of embedding vectors.
BatchEmbedding = list[EmbeddingVector]


class TextEmbedding(BaseModel):
    """Abstract base class for text embedding models.

    This class defines the interface that all text embedding implementations
    must follow. It provides validation for the embedding dimension and
    abstract methods for single and batch text embedding.

    Attributes:
        dimension: The dimensionality of the embedding vectors produced by this model.
                  Must be a positive integer.
    """

    model_config = ConfigDict(extra="forbid")
    dimension: int

    @field_validator("dimension")
    @classmethod
    def _positive_dimension(cls, value: int) -> int:
        """Validate that dimension is a positive integer.

        Args:
            value: The dimension value to validate.

        Returns:
            The validated dimension value.

        Raises:
            ValueError: If dimension is not positive.
        """
        if value <= 0:
            raise ValueError("dimension must be a positive integer")
        return value

    @abc.abstractmethod
    def embed(self, text: str) -> EmbeddingVector:
        """Embed a single text string into a vector.

        Args:
            text: The text to embed

        Returns:
            A list of floats representing the embedding vector
        """
        raise NotImplementedError

    @abc.abstractmethod
    def embed_batch(self, texts: Sequence[str]) -> BatchEmbedding:
        """Embed a batch of text strings into vectors.

        Args:
            texts: A list of texts to embed

        Returns:
            A list of embedding vectors, one for each input text
        """
        raise NotImplementedError


class OpenAITextEmbedding(TextEmbedding):
    """Text embeddings backed by OpenAI's embeddings API.

    This wrapper is intentionally small and user friendly:

    - Minimal configuration: only the ``model`` and (optionally) ``dimension``.
    - Lazy client creation: uses ``openai.OpenAI()`` with your environment
      configuration (e.g. ``OPENAI_API_KEY``, ``OPENAI_BASE_URL``).

    Attributes:
        client: The OpenAI client instance for making API calls.
        model: The OpenAI embedding model to use (default: "text-embedding-3-small").
        dimension: The embedding dimension (default: 1536 for text-embedding-3-small).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    client: OpenAI
    model: str = "text-embedding-3-small"
    dimension: int = 1536  # Default dimension for text-embedding-3-small

    def embed(self, text: str) -> EmbeddingVector:
        """Embed a single text string using OpenAI's API.

        Args:
            text: The text to embed.

        Returns:
            The embedding vector as a list of floats.
        """
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: Sequence[str]) -> BatchEmbedding:
        """Embed a batch of texts using OpenAI's API.

        Args:
            texts: A sequence of texts to embed.

        Returns:
            A list of embedding vectors, one for each input text.
        """
        if not texts:
            return []

        response = self.client.embeddings.create(
            model=self.model,
            input=list(texts),
            dimensions=self.dimension,
        )

        return [list(map(float, item.embedding)) for item in response.data]


class SentenceTransformerEmbedding(TextEmbedding):
    """Text embeddings backed by ``sentence-transformers``.

    - Model: any model name supported by ``SentenceTransformer``.
    - Device: ``"cpu"``, ``"cuda"``, ``"cuda:0"``, etc. (optional).
    - Batching: configurable ``batch_size``.
    - Normalisation: optional ``normalize_embeddings=True``.

    Attributes:
        model_name: The name of the sentence transformer model to use.
        device: The device to run the model on (CPU, CUDA, etc.).
        batch_size: The batch size for processing multiple texts.
        normalize_embeddings: Whether to normalize the embedding vectors.
        trust_remote_code: Whether to allow execution of remote model code.
        model: The loaded SentenceTransformer model instance.
        _dimension_cache: Cached dimension value for the model.
    """

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )

    model_name: str = "all-MiniLM-L6-v2"
    device: str | None = None
    batch_size: int = 32
    normalize_embeddings: bool = True
    trust_remote_code: bool = False
    model: Any = None
    _dimension_cache: int | None = None

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        *,
        device: str | None = None,
        batch_size: int = 32,
        normalize_embeddings: bool = True,
        trust_remote_code: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize the SentenceTransformer embedding model.

        Args:
            model_name: The name of the sentence transformer model.
            device: The device to run the model on.
            batch_size: The batch size for processing.
            normalize_embeddings: Whether to normalize embeddings.
            trust_remote_code: Whether to allow remote code execution for model
                loading when required by the selected model.
            **kwargs: Additional keyword arguments.

        Raises:
            ImportError: If sentence-transformers package is not installed.
            ValueError: If the model doesn't have a valid dimension.
        """
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except ImportError as exc:  # pragma: no cover - import error path
            raise ImportError(
                "SentenceTransformerEmbedding requires the 'sentence-transformers' "
                "package. Install it with "
                "`pip install 'sentence-transformers>=2.2.2,<3'` or enable the "
                "mdmodels[vector] extra."
            ) from exc

        model = SentenceTransformer(
            model_name,
            device=device,
            trust_remote_code=trust_remote_code,
        )
        dimension = model.get_sentence_embedding_dimension()
        if dimension is None:
            raise ValueError(f"Model {model_name} does not have a dimension")
        dimension = int(dimension)

        # Initialize with all declared fields
        super().__init__(
            dimension=dimension,
            model_name=model_name,  # type: ignore[arg-type]
            device=device,  # type: ignore[arg-type]
            batch_size=batch_size,  # type: ignore[arg-type]
            normalize_embeddings=normalize_embeddings,  # type: ignore[arg-type]
            trust_remote_code=trust_remote_code,  # type: ignore[arg-type]
            model=model,  # type: ignore[arg-type]
            **kwargs,
        )
        self._dimension_cache = dimension

    def embed(self, text: str) -> EmbeddingVector:
        """Embed a single text string using SentenceTransformer.

        Args:
            text: The text to embed.

        Returns:
            The embedding vector as a list of floats.
        """
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: Sequence[str]) -> BatchEmbedding:
        """Embed a batch of texts using SentenceTransformer.

        Args:
            texts: A sequence of texts to embed.

        Returns:
            A list of embedding vectors, one for each input text.
        """
        if not texts:
            return []

        # We request numpy arrays for efficient conversion to Python lists.
        embeddings = self.model.encode(
            list(texts),
            batch_size=self.batch_size,
            normalize_embeddings=self.normalize_embeddings,
            convert_to_numpy=True,
        )

        return [vec.astype(float).tolist() for vec in embeddings]

    @property
    def dimension(self) -> int:
        """Get the embedding dimension.

        Returns:
            The dimension of the embedding vectors.
        """
        assert self._dimension_cache is not None
        return self._dimension_cache


class FastembedTextEmbedding(TextEmbedding):
    """Text embeddings backed by ``fastembed.TextEmbedding``.

    This is a thin, convenient wrapper around fastembed:

    - Model: any ``fastembed`` text embedding model.
    - Batching: configurable ``batch_size`` for ``.embed(...)``.
    - Caching: optional ``cache_dir`` forwarded to fastembed.

    Attributes:
        model_name: The name of the fastembed model to use.
        cache_dir: Directory for caching model files.
        batch_size: The batch size for processing multiple texts.
        model: The loaded fastembed model instance.
        _dimension_cache: Cached dimension value for the model.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    model_name: str = "BAAI/bge-small-en-v1.5"
    cache_dir: str | None = None
    batch_size: int | None = None
    model: Any = None
    _dimension_cache: int | None = None

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-en-v1.5",
        *,
        cache_dir: str | None = None,
        batch_size: int | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the fastembed embedding model.

        Args:
            model_name: The name of the fastembed model.
            cache_dir: Directory for caching model files.
            batch_size: The batch size for processing.
            **kwargs: Additional keyword arguments.

        Raises:
            ImportError: If fastembed package is not installed.
            RuntimeError: If the model fails to produce embeddings.
        """
        try:
            from fastembed import TextEmbedding as _FastembedModel  # type: ignore
        except ImportError as exc:  # pragma: no cover - import error path
            raise ImportError(
                "FastembedTextEmbedding requires the 'fastembed' package. "
                "Install it with `pip install mdmodels[vector]` or "
                "`pip install 'fastembed>=0.7.3'`."
            ) from exc

        model = _FastembedModel(
            model_name=model_name,
            cache_dir=cache_dir,
            **{
                k: v
                for k, v in kwargs.items()
                if k not in ["model_name", "cache_dir", "batch_size"]
            },
        )

        # Calculate dimension upfront for initialization
        vectors = list(model.embed(["__dimension_probe__"]))
        if not vectors:
            raise RuntimeError(
                "fastembed failed to produce an embedding for the dimension probe."
            )
        dimension = int(len(vectors[0]))

        super().__init__(
            dimension=dimension,
            model_name=model_name,  # type: ignore[arg-type]
            cache_dir=cache_dir,  # type: ignore[arg-type]
            batch_size=batch_size,  # type: ignore[arg-type]
            model=model,  # type: ignore[arg-type]
            **{
                k: v
                for k, v in kwargs.items()
                if k not in ["model_name", "cache_dir", "batch_size"]
            },
        )
        self._dimension_cache = dimension

    def _ensure_dimension(self) -> None:
        """Infer and cache the embedding dimension lazily.

        Raises:
            RuntimeError: If the model fails to produce embeddings for dimension probing.
        """
        if self._dimension_cache is not None:
            return

        vectors = list(self.model.embed(["__dimension_probe__"]))
        if not vectors:
            raise RuntimeError(
                "fastembed failed to produce an embedding for the dimension probe."
            )

        first = vectors[0]
        # ``fastembed`` can return NumPy arrays or lists; both support ``len(...)``.
        self._dimension_cache = int(len(first))

    def embed(self, text: str) -> EmbeddingVector:
        """Embed a single text string using fastembed.

        Args:
            text: The text to embed.

        Returns:
            The embedding vector as a list of floats.
        """
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: Sequence[str]) -> BatchEmbedding:
        """Embed a batch of texts using fastembed.

        Args:
            texts: A sequence of texts to embed.

        Returns:
            A list of embedding vectors, one for each input text.
        """
        if not texts:
            return []

        embed_kwargs: dict[str, Any] = {}
        if self.batch_size is not None:
            embed_kwargs["batch_size"] = self.batch_size

        vectors = self.model.embed(
            list(texts),
            **embed_kwargs,
        )
        return [list(map(float, vec)) for vec in vectors]

    @property
    def dimension(self) -> int:
        """Get the embedding dimension, ensuring it's cached.

        Returns:
            The dimension of the embedding vectors.
        """
        self._ensure_dimension()
        assert self._dimension_cache is not None
        return self._dimension_cache
