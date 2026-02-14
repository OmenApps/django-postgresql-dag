"""Provides exceptions relevant to graphs."""


class NodeNotReachableException(Exception):
    """Exception raised when no path exists between two nodes."""

    pass


class GraphModelsCannotBeParsedException(Exception):
    """Exception raised when the provided model cannot be identified as a node or edge model."""

    pass


class IncorrectUsageException(Exception):
    """Exception raised when a function is called with incorrect arguments."""

    pass


class IncorrectQuerysetTypeException(Exception):
    """Exception for incorrect queryset type passed to transformation functions."""

    pass
