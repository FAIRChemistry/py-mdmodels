import os
import pytest
from neomodel import db

from mdmodels.graph import connect_to_neo4j, generate_neomodel


class TestGraph:
    @pytest.mark.expensive
    def test_queries(self):
        """
        Test the creation and relationship of graph entities in the database.

        This test verifies that a Person can be created and associated with
        multiple Hobby entities. It checks that the correct number of entities
        and relationships exist in the database after performing the operations.
        """
        # Arrange
        NEO4J_USER = os.getenv("NEO4J_USER")
        NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
        NEO4J_HOST = os.getenv("NEO4J_HOST")
        NEO4J_PORT = os.getenv("NEO4J_PORT")

        assert NEO4J_USER is not None, "NEO4J_USER is not set"
        assert NEO4J_PASSWORD is not None, "NEO4J_PASSWORD is not set"
        assert NEO4J_HOST is not None, "NEO4J_HOST is not set"
        assert NEO4J_PORT is not None, "NEO4J_PORT is not set"

        NEO4J_PORT = int(NEO4J_PORT)

        connect_to_neo4j(
            host=NEO4J_HOST,
            user=NEO4J_USER,
            password=NEO4J_PASSWORD,
            port=NEO4J_PORT,
        )

        # Clean up the database
        db.cypher_query("MATCH (n) DETACH DELETE n")

        # Act
        no4j_models = generate_neomodel(path="tests/fixtures/model_graph.md")
        Person = no4j_models["Person"]
        Hobby = no4j_models["Hobby"]

        person = Person(name="John", age=30)
        person.save()

        hiking = Hobby(name="Hiking")
        traveling = Hobby(name="Traveling")
        hiking.save()
        traveling.save()

        person.hobbies.connect(hiking)  # type: ignore
        person.dyn_connect(traveling, "LIKES_MOST", {"since": "2024-01-01"})

        # Assert
        person = Person.nodes.all()
        hobbies = Hobby.nodes.all()

        assert len(person) > 0, "There should be person"
        assert len(hobbies) > 0, "There should be hobbies"

        all_relationships = person[0].get_relationships()
        assert len(all_relationships) == 2, "There should be two relationships"

        _, rel, _ = all_relationships[-1]

        assert rel.type == "LIKES_MOST", "The relationship should be LIKES_MOST"
        assert (
            rel._properties["since"] == "2024-01-01"
        ), "The relationship should have the correct properties"
