# FastAPI Injector

![Workflow status](https://github.com/matyasrichter/fastapi-injector/actions/workflows/build.yml/badge.svg?branch=main)
[![Coverage status](https://coveralls.io/repos/github/matyasrichter/fastapi-injector/badge.svg)](https://coveralls.io/github/matyasrichter/fastapi-injector?branch=main)

Integrates [injector](https://github.com/alecthomas/injector) with [FastAPI](https://github.com/tiangolo/fastapi).

Github: https://github.com/matyasrichter/fastapi-injector  
PyPI: https://pypi.org/project/fastapi-injector/

## Installation

```shell
pip install fastapi-injector
```

## Usage

When creating your FastAPI app, attach the injector to it:

```python
# app.py
from fastapi import FastAPI
from injector import Injector
from fastapi_injector import attach_injector


def create_app(injector: Injector) -> FastAPI:
    app = FastAPI()
    app.include_router(...)
    ...
    attach_injector(app, injector)
    return app
```

Then, use `Injected` in your routes. Under the hood, `Injected` is `Depends`, so you can use it anywhere `Depends` can be used. In the following example, `InterfaceType` is
something you've bound an implementation to in your injector instance.

```python
from fastapi import APIRouter
from fastapi_injector import Injected

router = APIRouter()


@router.get("/")
async def get_root(integer: int = Injected(InterfaceType)):
    return integer
```

A more complete example could look like this (your FastAPI code only depends on `InterfaceType`,
its implementation only depends on a domain layer port etc.):

```python
# ------------------------
# interface.py
import abc
from abc import abstractmethod


class SomeInterface(abc.ABC):
    @abstractmethod
    async def create_some_entity(self) -> None:
        """Creates and saves an entity."""


# ------------------------
# service.py
import abc
from .interface import SomeInterface


class SomeSavePort(abc.ABC):
    @abc.abstractmethod
    async def save_something(self, something: Entity) -> None:
        """Saves an entity."""


class SomeService(SomeInterface):
    def __init__(self, save_port: Inject[SomeSavePort]):
        self.save_port = save_port

    async def create_some_entity(self) -> None:
        entity = Entity(attr1=1, attr2=2)
        await self.save_port.save_something(entity)


# ------------------------
# repository.py
from .service import SomeSavePort


class SomeRepository(SomeSavePort):
    async def save_something(self, something: Entity) -> None:
# code that saves the entity to the DB
```

## Testing with fastapi-injector

To use your app in tests with overridden dependencies, modify the injector before each test:

```python
# ------------------------
# app entrypoint
import pytest
from injector import Injector

app = create_app(inj)

if __name__ == "__main__":
    uvicorn.run("app", ...)


# ------------------------
# composition root
def create_injector() -> Injector:
    inj = Injector()
    # note that this still gets executed,
    # so if you need to get rid of a DB connection, for example,
    # you would need to use a callable provider.
    inj.binder.bind(int, 1)
    return inj


# ------------------------
# tests
from fastapi import FastAPI
from fastapi.testclient import TestClient
from path.to.app.factory import create_app


@pytest.fixture
def app() -> FastAPI:
    inj = Injector()
    inj.binder.bind(int, 2)
    return create_app(inj)


def some_test(app: FastAPI):
    # use test client with the new app
    client = TestClient(app)
```
