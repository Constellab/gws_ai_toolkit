from typing import Optional

from gws_core import LazyAbstractDbManager
from peewee import DatabaseProxy


class AiToolkitDbManager(LazyAbstractDbManager):
    """
    DbManager class.

    Provides backend features for managing databases.
    """

    db = DatabaseProxy()

    _instance: Optional["AiToolkitDbManager"] = None

    @classmethod
    def get_instance(cls) -> "AiToolkitDbManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_name(self) -> str:
        return "db"

    def get_brick_name(self) -> str:
        return "gws_ai_toolkit"
