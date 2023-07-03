from typing import Any, TypeVar

from fastapi import Depends
from starlette.requests import HTTPConnection

from fastapi_injector.attach import get_injector_instance

BoundInterface = TypeVar("BoundInterface", bound=type)


def Injected(interface: BoundInterface) -> Any:  # pylint: disable=invalid-name
    """
    Asks your injector instance for the specified type,
    allowing you to use it in the route.
    """

    async def inject_into_route(conn: HTTPConnection) -> BoundInterface:
        return get_injector_instance(conn.app).get(interface)

    return Depends(inject_into_route)


def SyncInjected(interface: BoundInterface) -> Any:  # pylint: disable=invalid-name
    """
    Asks your injector instance for the specified type,
    allowing you to use it in the route. Intended for use
    with synchronous interfaces.
    """

    def inject_into_route(conn: HTTPConnection) -> BoundInterface:
        return get_injector_instance(conn.app).get(interface)

    return Depends(inject_into_route)
