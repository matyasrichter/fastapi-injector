from fastapi import FastAPI
from injector import Injector, InstanceProvider, singleton

from fastapi_injector.exceptions import InjectorNotAttached
from fastapi_injector.request_scope import RequestScopeOptions


def attach_injector(app: FastAPI, injector: Injector, **kwargs) -> None:
    """
    Call this function on app startup to attach an injector to the app.

    Supported kwargs:
        * enable_cleanup

            If True, dependencies that were created from the request scope will be
            cleaned up when the scope is exited. Only dependencies that implement one
            of the context manager protocols will be considered for cleanup.
    """
    app.state.injector = injector
    options = RequestScopeOptions(**kwargs)
    injector.binder.bind(
        RequestScopeOptions, InstanceProvider(options), scope=singleton
    )


def get_injector_instance(app: FastAPI) -> Injector:
    """
    Returns the injector instance attached to the app.
    """
    try:
        return app.state.injector
    except AttributeError as exc:
        raise InjectorNotAttached(
            "No injector instance has been attached to the app."
        ) from exc
