from typing import Any, Type, TypeVar

from fastapi import Depends, Request, WebSocket
from injector import InstanceProvider
from starlette.requests import HTTPConnection

from fastapi_injector.attach import get_injector_instance
from fastapi_injector.request_scope import request_scope

T = TypeVar("T")


def _sync_bind_conn(conn: HTTPConnection) -> None:
    injector = get_injector_instance(conn.app)
    injector.binder.bind(HTTPConnection, InstanceProvider(conn), scope=request_scope)
    if isinstance(conn, Request):
        injector.binder.bind(Request, InstanceProvider(conn), scope=request_scope)
    elif isinstance(conn, WebSocket):
        injector.binder.bind(WebSocket, InstanceProvider(conn), scope=request_scope)


async def _bind_conn(conn: HTTPConnection) -> None:
    _sync_bind_conn(conn)


def SyncInjectConnection() -> Any:  # pylint: disable=invalid-name
    """
    Dependency to bind request-related instances to the injector.
    Intended to be used as a dependency of the FastAPI app instance.
    Intended for use with synchronous interfaces.
    """
    return Depends(_sync_bind_conn)


def InjectConnection() -> Any:  # pylint: disable=invalid-name
    """
    Dependency to bind request-related instances to the injector.
    Intended to be used as a dependency of the FastAPI app instance.
    """
    return Depends(_bind_conn)


def Injected(interface: Type[T]) -> T:  # pylint: disable=invalid-name
    """
    Asks your injector instance for the specified type,
    allowing you to use it in the route.
    """

    async def inject_into_route(conn: HTTPConnection) -> T:
        return get_injector_instance(conn.app).get(interface)

    return Depends(inject_into_route)


def SyncInjected(interface: Type[T]) -> T:  # pylint: disable=invalid-name
    """
    Asks your injector instance for the specified type,
    allowing you to use it in the route. Intended for use
    with synchronous interfaces.
    """

    def sync_inject_into_route(conn: HTTPConnection) -> T:
        return get_injector_instance(conn.app).get(interface)

    return Depends(sync_inject_into_route)
