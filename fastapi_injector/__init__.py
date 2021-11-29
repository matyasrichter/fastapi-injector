"""
A simple integration of alecthomas' injector into FastAPI.
Exposes a dependency wrapper to use in your routes.
"""

from typing import Any, TypeVar

from fastapi import Depends, FastAPI, Request
from injector import Injector


def attach_injector(app: FastAPI, injector: Injector) -> None:
    """Call this function on app startup to attach an injector to the app."""
    app.state.injector = injector


class RouteInjectionError(ValueError):
    """Raised when Injected is used without an injector instance attached to the app."""


BoundInterface = TypeVar("BoundInterface")


def Injected(interface: BoundInterface) -> Any:  # pylint: disable=invalid-name
    """
    Asks your injector instance for the specified type,
    allowing you to use it in the route.
    """

    def inject_into_route(request: Request) -> BoundInterface:
        try:
            return request.app.state.injector.get(interface)
        except AttributeError as exc:
            raise RouteInjectionError(
                "An injector instance has not been attached to the app."
            ) from exc

    return Depends(inject_into_route)


__all__ = [
    "attach_injector",
    "Injected",
    "RouteInjectionError",
]
