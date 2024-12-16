from sqlmodel import SQLModel


class SQLBase(SQLModel):
    """
    A base class for SQL models.
    """

    def to_dict(self):
        """
        Convert the SQLModel object to a dictionary.

        Returns:
            dict: The dictionary representation of the SQLModel object.
        """
        return self._to_dict_with_relationships(self)

    @classmethod
    def _to_dict_with_relationships(cls, obj):
        """
        Recursively serialize SQLModel objects including relationships.

        Args:
            obj: The SQLModel object or list of objects to serialize.

        Returns:
            dict or list: The serialized dictionary or list of dictionaries.
        """
        if isinstance(obj, list):
            return [cls._to_dict_with_relationships(o) for o in obj]
        elif isinstance(obj, SQLModel):
            data = obj.model_dump()
            for relation_name in obj.__class__.__annotations__:
                if relation_name not in data and hasattr(obj, relation_name):
                    if not getattr(obj, relation_name):
                        continue

                    data[relation_name] = cls._to_dict_with_relationships(
                        getattr(obj, relation_name)
                    )
            return data
        else:
            raise ValueError(f"Invalid object type: {type(obj)}")
