class MemoryService:
    """High-level memory operations for storing and retrieving memories.

    Implementations should accept a DB session or adapt to the project's
    `MemoryManager` implementation.
    """

    def __init__(self, db=None):
        self.db = db

    def store_memory(self, user_id: int, key: str, value: str, **kwargs):
        raise NotImplementedError()

    def get_memory(self, user_id: int, key: str):
        raise NotImplementedError()

    def list_memories(self, user_id: int):
        raise NotImplementedError()
