import logging
import asyncio
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class MultiplayerConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)
        self._metadata: dict[WebSocket, dict[str, Any]] = {}
        self._host_timeout_tasks: dict[int, asyncio.Task[None]] = {}
        self._host_timeout_versions: dict[int, int] = defaultdict(int)

    async def connect(
        self,
        room_id: int,
        websocket: WebSocket,
        *,
        user_id: int,
        is_host: bool,
    ) -> None:
        await websocket.accept()
        self._connections[room_id].add(websocket)
        self._metadata[websocket] = {
            'room_id': room_id,
            'user_id': user_id,
            'is_host': is_host,
        }
        if is_host:
            self.cancel_host_timeout(room_id)
        logger.info(
            'multiplayer_ws_connected room_id=%s connections=%s',
            room_id,
            len(self._connections[room_id]),
        )

    def disconnect(self, room_id: int, websocket: WebSocket) -> dict[str, Any]:
        metadata = self._metadata.pop(websocket, {})
        room_connections = self._connections.get(room_id)
        if room_connections is None:
            return metadata
        room_connections.discard(websocket)
        remaining = len(room_connections)
        if not room_connections:
            self._connections.pop(room_id, None)
        logger.info(
            'multiplayer_ws_disconnected room_id=%s connections=%s',
            room_id,
            remaining,
        )
        metadata['has_host_connection'] = self.has_host_connection(room_id)
        return metadata

    def has_host_connection(self, room_id: int) -> bool:
        for websocket in self._connections.get(room_id, ()):
            metadata = self._metadata.get(websocket) or {}
            if metadata.get('is_host') is True:
                return True
        return False

    def reset_host_timeout(
        self,
        room_id: int,
        *,
        delay_seconds: int,
        callback,
        force: bool = False,
    ) -> None:
        self.cancel_host_timeout(room_id)
        self.schedule_host_timeout(
            room_id,
            delay_seconds=delay_seconds,
            callback=callback,
            force=force,
            generation=self._host_timeout_versions[room_id],
        )

    def cancel_host_timeout(self, room_id: int) -> None:
        self._host_timeout_versions[room_id] += 1
        task = self._host_timeout_tasks.pop(room_id, None)
        if task is not None:
            task.cancel()

    def schedule_host_timeout(
        self,
        room_id: int,
        *,
        delay_seconds: int,
        callback,
        force: bool = False,
        generation: int | None = None,
    ) -> None:
        if room_id in self._host_timeout_tasks:
            return
        if generation is None:
            generation = self._host_timeout_versions[room_id]

        task_ref: asyncio.Task[None] | None = None

        async def _run() -> None:
            try:
                await asyncio.sleep(delay_seconds)
                if generation != self._host_timeout_versions[room_id]:
                    return
                if not force and self.has_host_connection(room_id):
                    return
                await callback(room_id, force=force)
            except asyncio.CancelledError:
                return
            finally:
                if self._host_timeout_tasks.get(room_id) is task_ref:
                    self._host_timeout_tasks.pop(room_id, None)

        task_ref = asyncio.create_task(_run())
        self._host_timeout_tasks[room_id] = task_ref
        logger.info(
            'multiplayer_host_timeout_scheduled room_id=%s delay_seconds=%s force=%s generation=%s',
            room_id,
            delay_seconds,
            force,
            generation,
        )

    async def broadcast(self, room_id: int, payload: dict[str, Any]) -> None:
        room_connections = list(self._connections.get(room_id, ()))
        logger.info(
            'multiplayer_ws_broadcast room_id=%s event=%s recipients=%s',
            room_id,
            payload.get('event'),
            len(room_connections),
        )
        for websocket in room_connections:
            try:
                await websocket.send_json(payload)
            except Exception:
                logger.exception(
                    'multiplayer_ws_broadcast_failed room_id=%s event=%s',
                    room_id,
                    payload.get('event'),
                )
                self.disconnect(room_id, websocket)


multiplayer_connection_manager = MultiplayerConnectionManager()
