import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict, Type

from injector import (
    Inject,
    Injector,
    InstanceProvider,
    Provider,
    Scope,
    ScopeDecorator,
    T,
)
from starlette.types import Receive, Send

from fastapi_injector.exceptions import RequestScopeError

_request_id_ctx: ContextVar[uuid.UUID] = ContextVar("request_id")


class RequestScope(Scope):
    """
    Caches dependencies within a single request.
    Needs the InjectorMiddleware to be installed to the FastAPI app.

    Example usage:
    ::
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
    """

    cache: Dict[uuid.UUID, Dict[Type, Any]]

    def __init__(self, injector: Injector) -> None:
        super().__init__(injector)
        self.cache = {}

    def get(self, key: Type[T], provider: Provider[T]) -> Provider[T]:
        try:
            request_id = _request_id_ctx.get()
        except LookupError as exc:
            raise RequestScopeError(
                "Request ID missing in cache. "
                "Make sure InjectorMiddleware has been added to the FastAPI instance."
            ) from exc
        if key in self.cache[request_id]:
            dependency = self.cache[request_id][key]
        else:
            dependency = provider.get(self.injector)
            self.cache[request_id][key] = dependency
        return InstanceProvider(dependency)

    def add_key(self, key: uuid.UUID) -> None:
        """Add a new request key to the cache."""
        self.cache[key] = {}

    def clear_key(self, key: uuid.UUID) -> None:
        """Clear the cache for a given request key."""
        del self.cache[key]


request_scope = ScopeDecorator(RequestScope)


class RequestScopeFactory:
    """
    Allows to create request scopes.
    """

    def __init__(self, request_scope_instance: Inject[RequestScope]) -> None:
        self.request_scope_instance = request_scope_instance

    @contextmanager
    def create_scope(self):
        """Creates a new request scope within dependencies are cached."""
        rid = uuid.uuid4()
        rid_ctx = _request_id_ctx.set(rid)
        self.request_scope_instance.add_key(rid)
        try:
            yield
        finally:
            self.request_scope_instance.clear_key(rid)
            _request_id_ctx.reset(rid_ctx)


class InjectorMiddleware:
    """
    Middleware that enables request-scoped injection through ContextVar-based cache.
    """

    def __init__(self, app, injector: Injector) -> None:
        self.app = app
        self.request_scope_factory = injector.get(RequestScopeFactory)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """
        Add an identifier to the request
        that can be used retrieve scoped dependencies.
        """
        with self.request_scope_factory.create_scope():
            await self.app(scope, receive, send)
