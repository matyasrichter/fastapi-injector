# FastAPI Injector

![Workflow status](https://github.com/matyasrichter/fastapi-injector/actions/workflows/test.yml/badge.svg?branch=main)
[![Coverage status](https://coveralls.io/repos/github/matyasrichter/fastapi-injector/badge.svg)](https://coveralls.io/github/matyasrichter/fastapi-injector?branch=main)
[![Version](https://img.shields.io/github/v/release/matyasrichter/fastapi-injector)](https://github.com/matyasrichter/fastapi-injector/releases/latest)

Integrates [injector](https://github.com/alecthomas/injector) with [FastAPI](https://github.com/tiangolo/fastapi).

Github: https://github.com/matyasrichter/fastapi-injector  
PyPI: https://pypi.org/project/fastapi-injector/

## Installation

```shell
pip install fastapi-injector
```

`fastapi-injector` relies on your project using FastAPI as a dependency separately, but you can also get it installed automatically by using any of the extras.

```shell
# Installs `fastapi`
pip install fastapi-injector[standard]

# Installs `fastapi-slim`
pip install fastapi-injector[slim]
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

Then, use `Injected` in your routes. Under the hood, `Injected` is `Depends`, so you can use it anywhere `Depends` can be used.

In the following example, an instance of something you've bound to `RandomNumberGenerator` is injected into the route - in this case, it's an implementation which uses the `random` module. Notice that only `app.py` (the 'composition root') has a dependency on the concrete generator implementation.

```python
# ------------------------
# generator.py
import abc

class RandomNumberGenerator(abc.ABC):
    @abc.abstractmethod
    def generate(self) -> int:
        pass


# ------------------------
# generator_impl.py
import random
from .generator import RandomNumberGenerator

class StdRandomNumberGenerator(RandomNumberGenerator):
    def generate(self) -> int:
       return random.randint(0,100)


# ------------------------
# app.py
from fastapi import FastAPI
from fastapi_injector import attach_injector
from injector import Injector

from .routers import generator_router
from .generator import RandomNumberGenerator
from .generator_impl import StdRandomNumberGenerator

app = FastAPI()
app.include_router(generator_router.router, prefix="/random")

inj = Injector()
inj.binder.bind(RandomNumberGenerator, to=StdRandomNumberGenerator)
attach_injector(app, inj)


# ------------------------
# routers/generator_router.py
from fastapi import APIRouter
from fastapi_injector import Injected

from ..generator import RandomNumberGenerator

router = APIRouter()

@router.get("/")
async def get_root(generator: RandomNumberGenerator = Injected(RandomNumberGenerator)) -> int:
    return generator.generate()
```

Here is another example. Imagine an onion-like architecture where your FastAPI code resides in the outer layer and your domain code ("use cases") are all defined in the inner layer. The usecases depend on interfaces that promise persistence, but the implementations (again, in the outer layer) are provided by dependency injection and the domain use case code knows nothing about them.
Some parts (such as imports, app initialization or the definition of User) are ommited here.

```python
# ------------------------
# usecase.py
class UserSavePort(abc.ABC):
    @abc.abstractmethod
    async def save_user(self, user: User) -> None:
        """Saves a user."""


class SignupUsecase:
    def __init__(self, save_port: Inject[UserSavePort]):
        self.save_port = save_port

    async def create_user(self, username: str) -> None:
        entity = User(username=username)
        await self.save_port.save_user(entity)


# ------------------------
# repository.py
class UserRepository(UserSavePort):
    async def save_user(self, user: Entity) -> None:
        # code that saves the entity to the DB, like a call to an ORM or a SQL query
        self.db.execute("INSERT INTO ...")

# ------------------------
# router.py
@router.post("/")
async def create_user(username: Annotated[str, Body()), uc: SignupUsecase = Injected(SignupUsecase)):
    await uc.create_user(username)

# ------------------------
# composition_root.py
inj = Injector(auto_bind=True)
inj.binder.bind(UserSavePort, to=UserRepository)
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

### Dependency cleanup
In some cases a request-scoped dependency may represent a resource that you wish to clean up in a deterministic manner at the end of the request scope. This might be because the resource is leased from a finite pool of such resources (e.g. a DB connection), and failure to release the resource in a timely manner could cause resource exhaustion. Typically, these resources will implement the [ContextManager protocol](https://docs.python.org/3/library/stdtypes.html#context-manager-types) so that they can be used with Python's `with` statement (or the async equivalent, `contextlib.AbstractAsyncContextManager`, which is used with the `async with` statement).

This library provides an option to perform cleanup on any dependency that implements one of the `ContextManager` protocols (either sync or async). To enable cleanup, set `enable_cleanup=True` when you attach the injector, as in the following example:

```python
from injector import Injector
from fastapi import FastAPI
from fastapi_injector import InjectorMiddleware, request_scope, attach_injector
from typing import TextIO

class ResourceFile:
    def __init__(self) -> None:
        self.file = None

    def __enter__(self) -> TextIO:
        self.file = open('resource.txt', 'r')
        return file

    def __exit__(self, *_args) -> None:
        self.file.close()

inj = Injector()
inj.binder.bind(ResourceFile, scope=request_scope)

app = FastAPI()
app.add_middleware(InjectorMiddleware, injector=inj)
options = RequestScopeOptions(enable_cleanup=True)
attach_injector(app, inj, options)
```

By setting `enable_cleanup=True` in the `RequestScopeOptions`, the library ensures that the `ResourceFile.__exit__()` function is called at the end of the request, meaning that the file resource is released.

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
