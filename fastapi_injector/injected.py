from inspect import Parameter, Signature
from typing import Annotated, Any, Type, TypeVar

from fastapi import Body, Depends, Request, WebSocket
from injector import InstanceProvider
from pydantic import BaseModel
from starlette.requests import HTTPConnection

from fastapi_injector.attach import get_injector_instance
from fastapi_injector.request_scope import request_scope

T = TypeVar("T")
M = TypeVar("M", bound=BaseModel)


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


def SyncInjectBody(interface: Type[M]) -> M:  # pylint: disable=invalid-name
    """
    Dependency to bind the deserialized pydantic body to the injector.
    Intended for use with synchronous interfaces.
    """

    def _sync_bind_body(**kwargs: Any) -> BaseModel:
        conn = kwargs["conn"]
        body = kwargs["body"]
        injector = get_injector_instance(conn.app)
        injector.binder.bind(BaseModel, InstanceProvider(body), scope=request_scope)
        return body

    # workaround to allow for dynamic typing of the body in the function
    # https://github.com/fastapi/fastapi/issues/2901#issuecomment-791593780
    # https://github.com/python/typing/issues/598
    _sync_bind_body.__signature__ = Signature(  # type: ignore[attr-defined]
        [
            Parameter(
                name="conn",
                kind=Parameter.POSITIONAL_OR_KEYWORD,
                annotation=HTTPConnection,
            ),
            Parameter(
                name="body",
                kind=Parameter.POSITIONAL_OR_KEYWORD,
                annotation=Annotated[interface, Body()],
            ),
        ],
        return_annotation=interface,
    )

    return Depends(_sync_bind_body)


def InjectBody(interface: Type[M]) -> M:  # pylint: disable=invalid-name
    """
    Dependency to bind the deserialized pydantic body to the injector.
    """

    async def _bind_body(**kwargs: Any) -> BaseModel:
        conn = kwargs["conn"]
        body = kwargs["body"]
        injector = get_injector_instance(conn.app)
        injector.binder.bind(BaseModel, InstanceProvider(body), scope=request_scope)
        return body

    # workaround to allow for dynamic typing of the body in the function
    # https://github.com/fastapi/fastapi/issues/2901#issuecomment-791593780
    # https://github.com/python/typing/issues/598
    _bind_body.__signature__ = Signature(  # type: ignore[attr-defined]
        [
            Parameter(
                name="conn",
                kind=Parameter.POSITIONAL_OR_KEYWORD,
                annotation=HTTPConnection,
            ),
            Parameter(
                name="body",
                kind=Parameter.POSITIONAL_OR_KEYWORD,
                annotation=Annotated[interface, Body()],
            ),
        ],
        return_annotation=interface,
    )

    return Depends(_bind_body)


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
