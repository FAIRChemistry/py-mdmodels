import os
from mdmodels import DataModel, llm


class TestLLM:
    def test_llm(self):
        # Arrange
        OLLAMA_HOST = os.getenv("OLLAMA_HOST")
        OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")

        assert OLLAMA_HOST, "OLLAMA_HOST is not set"
        assert OLLAMA_MODEL, "OLLAMA_MODEL is not set"

        dm = DataModel.from_markdown("./tests/fixtures/model_graph.md")
        input_text = "My name is John Doe (33 yrs old) and I like to code."

        # Act
        response = llm.query_openai(
            query=input_text,
            response_model=dm.Person,
            base_url=OLLAMA_HOST,
            llm_model=OLLAMA_MODEL,
            api_key="ollama",
        )

        # Assert
        assert response
