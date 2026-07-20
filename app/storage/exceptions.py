class StorageError(Exception):
    """Base storage error safe to surface as a generic operation failure."""


class StorageConfigurationError(StorageError):
    pass


class StorageValidationError(StorageError):
    pass


class StorageAuthorizationError(StorageError):
    pass


class StorageNotFoundError(StorageError):
    pass
