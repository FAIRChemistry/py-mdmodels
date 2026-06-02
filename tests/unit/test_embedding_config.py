import sys
import types

import pytest

from mdmodels.config import AppConfig, OpenAIEmbeddingConfig, SQLEmbeddingConfig
from mdmodels.sql.config import TableConfig
from mdmodels.sql.vector import SentenceTransformerEmbedding, TextEmbedding


class DummyTextEmbedding(TextEmbedding):
    model_name: str
    cache_dir: str | None = None
    batch_size: int | None = None
    trust_remote_code: bool = False

    def embed(self, text: str):
        return [0.0] * self.dimension

    def embed_batch(self, texts):
        return [[0.0] * self.dimension for _ in texts]


def test_sentence_transformer_embedding_accepts_dimension_cache_and_custom_code(
    monkeypatch,
):
    class FakeSentenceTransformer:
        init_kwargs = {}

        def __init__(self, model_name, device=None, trust_remote_code=False):
            FakeSentenceTransformer.init_kwargs = {
                "model_name": model_name,
                "device": device,
                "trust_remote_code": trust_remote_code,
            }

        def get_sentence_embedding_dimension(self):
            return 768

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        types.SimpleNamespace(SentenceTransformer=FakeSentenceTransformer),
    )

    embedding = SentenceTransformerEmbedding(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        trust_remote_code=True,
    )

    assert embedding.dimension == 768
    assert FakeSentenceTransformer.init_kwargs["trust_remote_code"] is True


def test_sql_embedding_config_rejects_mixed_fastembed_provider_sections():
    with pytest.raises(
        ValueError,
        match="embedding\\.openai and embedding\\.huggingface are not allowed",
    ):
        SQLEmbeddingConfig(
            column="description",
            model="BAAI/bge-small-en-v1.5",
            provider="fastembed",
            openai=OpenAIEmbeddingConfig(),
        )


def test_table_config_builds_fastembed_model(monkeypatch):
    captured = {}

    def fake_fastembed(model_name, cache_dir=None, batch_size=None):
        captured.update(
            {
                "model_name": model_name,
                "cache_dir": cache_dir,
                "batch_size": batch_size,
            }
        )
        return DummyTextEmbedding(
            dimension=768,
            model_name=model_name,
            cache_dir=cache_dir,
            batch_size=batch_size,
        )

    monkeypatch.setattr("mdmodels.sql.config.FastembedTextEmbedding", fake_fastembed)

    config = AppConfig.model_validate(
        {
            "model": {"path": "specifications/model.md"},
            "sql": {
                "type": "pgvector",
                "tables": {
                    "StrendaBiocatalysis": {
                        "embedding": {
                            "column": "description",
                            "provider": "fastembed",
                            "model": "jinaai/jina-embeddings-v2-base-code",
                            "dimension": 768,
                            "fastembed": {
                                "cache_dir": "/tmp/emb-cache",
                                "batch_size": 16,
                            },
                        }
                    }
                },
            },
        }
    )

    table_config = TableConfig.from_config(config, "StrendaBiocatalysis")
    assert isinstance(table_config.embed_model, DummyTextEmbedding)
    assert captured == {
        "model_name": "jinaai/jina-embeddings-v2-base-code",
        "cache_dir": "/tmp/emb-cache",
        "batch_size": 16,
    }


def test_table_config_passes_trust_remote_code_to_huggingface(monkeypatch):
    captured = {}

    def fake_sentence_transformer(
        model_name,
        device=None,
        batch_size=32,
        normalize_embeddings=True,
        trust_remote_code=False,
    ):
        captured.update(
            {
                "model_name": model_name,
                "device": device,
                "batch_size": batch_size,
                "normalize_embeddings": normalize_embeddings,
                "trust_remote_code": trust_remote_code,
            }
        )
        return DummyTextEmbedding(
            dimension=768,
            model_name=model_name,
            trust_remote_code=trust_remote_code,
        )

    monkeypatch.setattr(
        "mdmodels.sql.config.SentenceTransformerEmbedding", fake_sentence_transformer
    )

    config = AppConfig.model_validate(
        {
            "model": {"path": "specifications/model.md"},
            "sql": {
                "type": "pgvector",
                "tables": {
                    "StrendaBiocatalysis": {
                        "embedding": {
                            "column": "description",
                            "provider": "huggingface",
                            "model": "jinaai/jina-embeddings-v2-base-code",
                            "dimension": 768,
                            "huggingface": {
                                "trust_remote_code": True,
                            },
                        }
                    }
                },
            },
        }
    )

    table_config = TableConfig.from_config(config, "StrendaBiocatalysis")
    assert isinstance(table_config.embed_model, DummyTextEmbedding)
    assert captured["trust_remote_code"] is True
