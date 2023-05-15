import abc
import asyncio
import time
import uuid
from typing import Tuple

import httpx
import pytest
from fastapi import FastAPI
from injector import Injector, inject
from starlette import status

from fastapi_injector import (
    Injected,
    InjectorMiddleware,
    RequestScope,
    RequestScopeFactory,
    attach_injector,
    request_scope,
)
from fastapi_injector.exceptions import InjectorNotAttached, RequestScopeError


@pytest.fixture
def app_inj() -> Tuple[FastAPI, Injector]:
    inj = Injector()
    app = FastAPI()
    app.add_middleware(InjectorMiddleware, injector=inj)
    attach_injector(app, inj)
    return app, inj


@pytest.mark.asyncio
async def test_caches_instance(app_inj):
    class DummyInterface:
        pass

    class DummyImpl:
        pass

    app, inj = app_inj
    inj.binder.bind(DummyInterface, to=DummyImpl, scope=request_scope)

    @app.get("/")
    def get_root(
        dummy: DummyInterface = Injected(DummyInterface),
        dummy2: DummyInterface = Injected(DummyInterface),
    ):
        assert dummy is dummy2

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        r = await client.get("/")
    assert r.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_caches_instance_nested(app_inj):
    class DummyInterface:
        pass

    class DummyImpl:
        pass

    class DummyInterface2:
        @abc.abstractmethod
        def get_dummy(self) -> DummyInterface:
            pass

    class DummyImpl2:
        @inject
        def __init__(self, dummy: DummyInterface):
            self.dummy = dummy

        def get_dummy(self) -> DummyInterface:
            return self.dummy

    app, inj = app_inj
    inj.binder.bind(DummyInterface, to=DummyImpl, scope=request_scope)
    inj.binder.bind(DummyInterface2, to=DummyImpl2)

    @app.get("/")
    def get_root(
        dummy: DummyInterface = Injected(DummyInterface),
        dummy2: DummyInterface2 = Injected(DummyInterface2),
    ):
        assert dummy is not dummy2
        assert dummy is dummy2.get_dummy()

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        r = await client.get("/")
    assert r.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_doesnt_cache_across_requests(app_inj):
    class DummyInterface:
        id: uuid.UUID

    class DummyImpl:
        def __init__(self):
            self.id = uuid.uuid4()

    app, inj = app_inj
    inj.binder.bind(DummyInterface, to=DummyImpl, scope=request_scope)

    @app.get("/")
    def get_root(
        dummy: DummyInterface = Injected(DummyInterface),
        dummy2: DummyInterface = Injected(DummyInterface),
    ):
        assert dummy.id == dummy2.id
        return {"dummy": dummy.id}

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        r = await client.get("/")
        r2 = await client.get("/")
    assert r.status_code == status.HTTP_200_OK
    assert r2.status_code == status.HTTP_200_OK
    assert r.json()["dummy"] != r2.json()["dummy"]


@pytest.mark.asyncio
async def test_doesnt_cache_across_concurrent_requests(app_inj):
    class DummyInterface:
        id: uuid.UUID

    class DummyImpl:
        def __init__(self):
            self.id = uuid.uuid4()

    app, inj = app_inj
    inj.binder.bind(DummyInterface, to=DummyImpl, scope=request_scope)

    @app.get("/")
    def get_root(dummy: DummyInterface = Injected(DummyInterface)):
        time.sleep(0.5)
        return {"dummy": dummy.id}

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        r = client.get("/")
        await asyncio.sleep(0.1)
        r2 = client.get("/")
        results = await asyncio.gather(r, r2)
    assert results[0].json()["dummy"] != results[1].json()["dummy"]


async def test_middleware_not_added():
    class DummyInterface:
        pass

    class DummyImpl:
        pass

    inj = Injector()
    app = FastAPI()
    attach_injector(app, inj)
    inj.binder.bind(DummyInterface, to=DummyImpl, scope=request_scope)

    @app.get("/")
    def get_root(dummy: DummyInterface = Injected(DummyInterface)):
        return {"dummy": str(dummy)}

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        with pytest.raises(RequestScopeError):
            await client.get("/")


async def test_middleware_added_without_injector_attached():
    class DummyInterface:
        pass

    class DummyImpl:
        pass

    inj = Injector()
    app = FastAPI()
    app.add_middleware(InjectorMiddleware, injector=inj)
    inj.binder.bind(DummyInterface, to=DummyImpl, scope=request_scope)

    @app.get("/")
    def get_root(dummy: DummyInterface = Injected(DummyInterface)):
        return {"dummy": str(dummy)}

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        with pytest.raises(InjectorNotAttached):
            await client.get("/")


async def test_request_scope_cache_cleared(app_inj):
    class DummyInterface:
        pass

    class DummyImpl:
        pass

    app, inj = app_inj
    inj.binder.bind(DummyInterface, to=DummyImpl, scope=request_scope)

    @app.get("/")
    def get_root(
        dummy: DummyInterface = Injected(DummyInterface),
        dummy2: DummyInterface = Injected(DummyInterface),
    ):
        assert dummy is dummy2
        return {"dummy": str(dummy)}

    scope_instance = inj.get(RequestScope)
    assert len(scope_instance.cache) == 0
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        await client.get("/")

    assert len(scope_instance.cache) == 0


async def test_caches_instances_with_scope_factory():
    class DummyInterface:
        pass

    class DummyImpl:
        pass

    inj = Injector()
    inj.binder.bind(DummyInterface, to=DummyImpl, scope=request_scope)

    factory = inj.get(RequestScopeFactory)

    with factory.create_scope():
        dummy1 = inj.get(DummyInterface)
        dummy2 = inj.get(DummyInterface)
        assert dummy1 is dummy2

    with factory.create_scope():
        dummy3 = inj.get(DummyInterface)
        assert dummy1 is not dummy3
