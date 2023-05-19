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

## Request scope
A common requirement is to have a dependency resolved to the same instance multiple times in the same request,
but to create new instances for other requests. An example usecase for this behaviour 
is managing per-request DB connections.

This library provides a `RequestScope` that fulfills this requirement.
Under the hood, it uses [Context Variables](https://docs.python.org/3/library/contextvars.html)
introduced in Python 3.7, generates a UUID4 for each request, and caches dependencies in a dictionary
with this uuid as the key.

```python
from injector import Injector
from fastapi import FastAPI
from fastapi_injector import InjectorMiddleware, request_scope, attach_injector

from foo.bar import Interface, Implementation

inj = Injector()
# Use request_scope when binding the dependency
inj.binder.bind(Interface, to=Implementation, scope=request_scope)

app = FastAPI()
# Add the injector middleware to the app instance
app.add_middleware(InjectorMiddleware, injector=inj)
attach_injector(app, inj)
```

Your dependencies will then be cached within a request's resolution tree.
Caching works both for top-level and nested dependencies
(e.g. when you inject a DB connection to multiple repository classes).

```python
@app.get("/")
def get_root(
    foo: Interface = Injected(Interface),
    bar: Interface = Injected(Interface),
):
    # the following assert will pass because both are the same instance.
    assert foo is bar
```

Outside of FastAPI routes, you can use `RequestScopeFactory.create_scope`, which returns a context manager that substitutes `InjectorMiddleware`.
This is useful in celery tasks, cron jobs, CLI commands and other parts of your application outside of the request-response cycle.

```python
class MessageHandler:
    def __init__(self, request_scope_factory: Inject[RequestScopeFactory]) -> None:
        self.request_scope_factory = request_scope_factory

    async def handle(self, message: Any) -> None:
        with self.request_scope_factory.create_scope():
            # process message
```

### SyncInjected
The dependency constructed by `Injected` is asynchronous. This causes it to run on the main thread. Should your usecase require a synchronous dependency, there's also an alternative - `SyncInjected`. Synchronous dependencies created by `SyncInjected` will be run on a separate thread from the threadpool. See the [FastAPI docs on this behaviour](https://fastapi.tiangolo.com/async/#dependencies).

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

## Contributing
All contributions are welcome. Please raise an issue and/or open a pull request if you'd like to help to make `fastapi-injector` better.
- Use [poetry](https://python-poetry.org/docs/) to install dependencies
- Use [pre-commit](https://pre-commit.com/) to run linters and formatters before committing and pushing
- Write tests for your code
