import asyncio
import threading
import typing

import httpx
import pytest
from fastapi import APIRouter, Depends, FastAPI, Request, Response, status
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket
from injector import Injector, Module, provider
from pydantic import BaseModel
from starlette.requests import HTTPConnection

from fastapi_injector import (
    InjectBody,
    InjectConnection,
    Injected,
    InjectorMiddleware,
    InjectorNotAttached,
    SyncInjectBody,
    SyncInjected,
    attach_injector,
    get_injector_instance,
    request_scope,
)

ReqType = typing.NewType("ReqType", str)
WsType = typing.NewType("WsType", str)

BIND_INT_TO: int = 1
BIND_STR_TO: str = "some_string"
BIND_STR_TYPE_TO: str = "some_string_for_type"
BIND_BYTES_TO: bytes = b"some_bytes"


class MyModel(BaseModel):
    value: bytes


class MyModule(Module):
    @provider
    def is_main_thread(self) -> bool:
        return threading.current_thread() is threading.main_thread()

    @provider
    def event_loop(self) -> asyncio.AbstractEventLoop:
        return asyncio.get_event_loop()

    @provider
    @request_scope
    def conn_value(self, conn: HTTPConnection) -> str:
        return conn.query_params["conn"]

    @provider
    @request_scope
    def request_value(self, request: Request) -> ReqType:
        return ReqType(request.query_params["req"])

    @provider
    @request_scope
    def ws_value(self, websocket: WebSocket) -> WsType:
        return WsType(websocket.query_params["ws"])

    @provider
    @request_scope
    def body_value(self, body: BaseModel) -> bytes:
        assert isinstance(body, MyModel)
        return body.value


@pytest.fixture
def app() -> FastAPI:
    inj = Injector(MyModule())
    inj.binder.bind(int, to=BIND_INT_TO)
    app = FastAPI(dependencies=[InjectConnection()])
    app.add_middleware(InjectorMiddleware, injector=inj)
    attach_injector(app, inj)
    return app


@pytest.mark.asyncio
async def test_route_injection(app):
    @app.post("/", dependencies=[InjectBody(MyModel)])
    def post_root(
        request: Request,
        integer: int = Injected(int),
        string: str = Injected(str),
        bts: bytes = Injected(bytes),
        req: ReqType = Injected(ReqType),
    ):
        return {
            "int": integer,
            "str": string,
            "req": req,
            "bytes": bts.decode(),
        }

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/?req={}&conn={}".format(BIND_STR_TYPE_TO, BIND_STR_TO),
            json={
                "value": BIND_BYTES_TO.decode(),
            },
        )
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "int": BIND_INT_TO,
        "str": BIND_STR_TO,
        "req": BIND_STR_TYPE_TO,
        "bytes": BIND_BYTES_TO.decode(),
    }


@pytest.mark.asyncio
async def test_route_body_injection(app):
    @app.post("/")
    def post_root(
        body: MyModel = InjectBody(MyModel),
        bts: bytes = Injected(bytes),
    ):
        assert isinstance(body, MyModel)
        assert body.value == bts
        return {
            "bytes": body.value.decode(),
        }

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/",
            json={
                "value": BIND_BYTES_TO.decode(),
            },
        )
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "bytes": BIND_BYTES_TO.decode(),
    }


@pytest.mark.asyncio
async def test_route_body_injection_sync(app):
    @app.post("/")
    def post_root(
        body: MyModel = SyncInjectBody(MyModel),
        bts: bytes = SyncInjected(bytes),
    ):
        assert isinstance(body, MyModel)
        assert body.value == bts
        return {
            "bytes": body.value.decode(),
        }

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/",
            json={
                "value": BIND_BYTES_TO.decode(),
            },
        )
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "bytes": BIND_BYTES_TO.decode(),
    }


def test_route_injection_websocket(app):
    @app.websocket("/")
    async def ws(
        websocket: WebSocket,
        integer: int = Injected(int),
        string: str = Injected(str),
        ws: WsType = Injected(WsType),
    ):
        await websocket.accept()
        await websocket.send_json(
            {
                "int": integer,
                "str": string,
                "ws": ws,
            }
        )
        await websocket.close()

    client = TestClient(app)
    with client.websocket_connect(
        "/?ws={}&conn={}".format(BIND_STR_TYPE_TO, BIND_STR_TO),
    ) as websocket:
        assert websocket.receive_json() == {
            "int": BIND_INT_TO,
            "str": BIND_STR_TO,
            "ws": BIND_STR_TYPE_TO,
        }


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
