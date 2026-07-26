"""Turn unhandled route exceptions into responses the browser can actually read.

Starlette builds the 500 for an unhandled exception in ``ServerErrorMiddleware``, which sits
*outside* every application middleware — ``CORSMiddleware`` included. The response therefore
leaves the server with no ``Access-Control-Allow-Origin`` header, the browser rejects it
before JavaScript sees it, and the frontend reports an opaque network failure instead of the
server fault that actually happened. That is how a simulation tick blowing up on a duplicate
key reached the operator as "load failed".

Converting the exception to a response *underneath* the CORS layer fixes it: CORS then
decorates the 500 exactly like any other response, and the frontend can show a real error.
The exception is logged with its traceback here, so nothing is lost by not re-raising.
"""

from __future__ import annotations

import logging

from aegis_contracts.errors import ApiErrorEnvelopeV1
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)

_INTERNAL_ERROR_BODY = ApiErrorEnvelopeV1(
    schema_version=1,
    code="INTERNAL_ERROR",
    # Deliberately generic: the traceback goes to the server log, never to the client.
    message="The server failed to handle the request.",
).model_dump(by_alias=True)


class UnhandledErrorMiddleware:
    """Render unhandled exceptions as a 500 inside the middleware stack.

    Must be installed *below* ``CORSMiddleware`` — with Starlette's ``add_middleware``
    prepending to the stack, that means adding it before CORS in ``create_app``.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        response_started = False

        async def _send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self._app(scope, receive, _send)
        except Exception:
            logger.exception(
                "Unhandled error serving %s %s",
                scope.get("method", "?"),
                scope.get("path", "?"),
            )
            if response_started:
                # Status and headers are already on the wire; the only honest thing left is
                # to let the server error handler tear the connection down.
                raise
            response = JSONResponse(status_code=500, content=_INTERNAL_ERROR_BODY)
            await response(scope, receive, send)
