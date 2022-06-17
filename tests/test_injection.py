import httpx
import pytest
from fastapi import APIRouter, Depends, FastAPI, Response, status
from injector import Injector

from fastapi_injector import (
    Injected,
    InjectorNotAttached,
    attach_injector,
    get_injector_instance,
)

BIND_INT_TO: int = 1


@pytest.fixture
def app() -> FastAPI:
    inj = Injector()
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
