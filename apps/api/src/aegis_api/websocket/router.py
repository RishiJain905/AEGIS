"""FastAPI WebSocket routes."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket

from aegis_api.websocket.manager import WebSocketGatewayManager

router = APIRouter(tags=["websocket"])


def create_websocket_router(manager: WebSocketGatewayManager) -> APIRouter:
    ws_router = APIRouter(tags=["websocket"])

    @ws_router.websocket(manager.config.ws_path)
    async def realtime_gateway(websocket: WebSocket) -> None:
        await manager.handle_connection(websocket)

    return ws_router
