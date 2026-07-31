class StorageError(Exception):
    """Base storage error safe to surface as a generic operation failure."""


class StorageConfigurationError(StorageError):
    pass


class StorageValidationError(StorageError):
    pass


class StorageUploadContractError(StorageValidationError):
    """A safe, structured application error for Company Media upload APIs."""

    def __init__(self, code, message, *, details=None, retryable=False, status_code=422):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.retryable = bool(retryable)
        self.status_code = status_code


class StorageAuthorizationError(StorageError):
    pass


class StorageNotFoundError(StorageError):
    pass
