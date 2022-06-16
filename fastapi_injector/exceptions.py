class InjectorNotAttached(ValueError):
    """Raised when Injected is used without an injector instance attached to the app."""


class RequestScopeError(ValueError):
    """Raised for RequestScope-related errors."""
