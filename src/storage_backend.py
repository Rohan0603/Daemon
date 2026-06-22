from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class StorageBackend(ABC):
    """Abstract base class defining the unified interface for all persistent stores."""

    @abstractmethod
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a single entry by its unique key/ID.

        Args:
            key: The unique identifier for the entry.

        Returns:
            A dictionary representing the entry (e.g., with keys "id", "content", "timestamp")
            or None if the entry does not exist.
        """
        pass

    @abstractmethod
    def set(self, key: str, data: Dict[str, Any]) -> bool:
        """
        Store or update an entry with the given key.

        Args:
            key: The unique identifier for the entry.
            data: A dictionary representing the entry data. Expected to contain
                  at least "content" and optionally "timestamp".

        Returns:
            True if the operation succeeded, False otherwise.
        """
        pass

    @abstractmethod
    def query(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Query the store for entries matching the specified filters.

        Args:
            filters: A dictionary of key-value pairs to filter by.

        Returns:
            A list of dictionaries representing the matching entries.
            Each entry typically has keys: "id", "content", "timestamp".
        """
        pass

    @abstractmethod
    def all_entries(self) -> List[Dict[str, Any]]:
        """
        Retrieve all entries currently in the store.

        Returns:
            A list of all entries, where each entry is a dictionary with keys:
            "id", "content", "timestamp".
        """
        pass

    @abstractmethod
    def count(self) -> int:
        """
        Return the total number of entries in the store.

        Returns:
            The number of entries.
        """
        pass
