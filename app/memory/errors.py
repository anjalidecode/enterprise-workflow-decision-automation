"""Memory-layer errors."""


class MemoryError(Exception):
    """Base memory error."""


class MemorySafetyError(MemoryError):
    """Long-term write rejected because of unsafe or disallowed content."""


class MemoryPermissionError(MemoryError):
    """Agent is not allowed to use this memory layer/operation."""
