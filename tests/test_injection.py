import asyncio
import httpx
import pytest
import threading


from fastapi import APIRouter, Depends, FastAPI, Response, status
from injector import provider, Injector, Module

from fastapi_injector import (
    Injected,
    SyncInjected,
    InjectorNotAttached,
    attach_injector,
    get_injector_instance,
)

BIND_INT_TO: int = 1


class MyModule(Module):
    @provider
    def is_main_thread(self) -> bool:
        return threading.current_thread() is threading.main_thread()

    @provider
    def event_loop(self) -> asyncio.AbstractEventLoop:
        return asyncio.get_event_loop()


@pytest.fixture
def app() -> FastAPI:
    inj = Injector(MyModule())
    inj.binder.bind(int, to=BIND_INT_TO)
    app = FastAPI()
    attach_injector(app, inj)
    return app


@pytest.mark.asyncio
async def test_route_injection(app):
    @app.get("/")
    def get_root(integer: int = Injected(int)):
        return integer

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == BIND_INT_TO


@pytest.mark.asyncio
async def test_router_injection(app):
    async def attach_to_response(response: Response, integer: int = Injected(int)):
        response.headers["X-Integer"] = str(integer)

    router = APIRouter(dependencies=[Depends(attach_to_response)])

    @router.get("/")
    def get_root():
        pass

    app.include_router(router)

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        r = await client.get("/")
    assert r.status_code == status.HTTP_200_OK
    assert r.headers["X-Integer"] == str(BIND_INT_TO)


@pytest.mark.asyncio
async def test_router_injection_sync(app):
    async def attach_to_response(
        response: Response, is_main_thread: bool = SyncInjected(bool)
    ):
        response.headers["X-Main"] = str(is_main_thread)

    router = APIRouter(dependencies=[Depends(attach_to_response)])

    @router.get("/")
    def get_root():
        pass

    app.include_router(router)

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        r = await client.get("/")
    assert r.headers["X-Main"] == "False"


@pytest.mark.asyncio
async def test_router_injection_async(app):
    async def attach_to_response(
        response: Response,
        is_main_thread: bool = Injected(bool),
    ):
        response.headers["X-Main"] = str(is_main_thread)

    router = APIRouter(dependencies=[Depends(attach_to_response)])

    @router.get("/")
    def get_root():
        pass

    app.include_router(router)

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        r = await client.get("/")
    assert r.headers["X-Main"] == "True"


@pytest.mark.asyncio
async def test_router_injection_can_access_event_loop(app):
    router = APIRouter()

    @router.get("/")
    def get_root(
        event_loop: asyncio.AbstractEventLoop = Injected(asyncio.AbstractEventLoop),
    ):
        pass

    app.include_router(router)

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        # will raise an exception when run synchronously
        await client.get("/")


@pytest.mark.asyncio
async def test_not_attached():
    app = FastAPI()

    @app.get("/")
    def get_root(integer: int = Injected(int)):
        pass

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        with pytest.raises(InjectorNotAttached):
            await client.get("/")


def test_get_injector_instance():
    inj = Injector()
    app = FastAPI()
    attach_injector(app, inj)
    assert get_injector_instance(app) is inj


def test_get_injector_instance_not_attached():
    app = FastAPI()
    with pytest.raises(InjectorNotAttached):
        get_injector_instance(app)
