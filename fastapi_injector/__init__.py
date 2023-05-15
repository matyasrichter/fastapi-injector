"""
A simple integration of alecthomas' injector into FastAPI.
Exposes a dependency wrapper to use in your routes.
"""

from fastapi_injector.attach import attach_injector, get_injector_instance
from fastapi_injector.exceptions import InjectorNotAttached
from fastapi_injector.injected import Injected, SyncInjected
from fastapi_injector.request_scope import (
    InjectorMiddleware,
    RequestScope,
    RequestScopeFactory,
    request_scope,
)

__all__ = [
    "attach_injector",
    "get_injector_instance",
    "Injected",
    "SyncInjected",
    "InjectorNotAttached",
    "request_scope",
    "RequestScope",
    "RequestScopeFactory",
    "InjectorMiddleware",
]
