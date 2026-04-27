import unittest
import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.endpoints.multiplayer import routes as multiplayer_routes
from app.api.endpoints.multiplayer.internals import commands as multiplayer_commands
from app.api.endpoints.multiplayer.internals import (
    host_timeout as multiplayer_host_timeout,
)
from app.api.endpoints.multiplayer.internals import websocket as multiplayer_websocket
from app.services.multiplayer.realtime import MultiplayerConnectionManager


class _DummySession:
    def close(self) -> None:
        return None


class MultiplayerWebSocketTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = FastAPI()
        self.app.include_router(multiplayer_routes.router, prefix='/multiplayer')
        self.app.dependency_overrides[multiplayer_routes.require_full_access] = (
            lambda: {'hasFullAccess': True}
        )
        self.client = TestClient(self.app)

        self._original_authenticate = multiplayer_websocket.authenticate_websocket
        self._original_websocket_session_local = multiplayer_websocket.SessionLocal
        self._original_host_timeout_session_local = multiplayer_host_timeout.SessionLocal
        self._original_websocket_get_room_by_id = multiplayer_websocket.get_room_by_id
        self._original_commands_get_room_by_id = multiplayer_commands.get_room_by_id
        self._original_host_timeout_get_room_by_id = multiplayer_host_timeout.get_room_by_id
        self._original_routes_get_room_by_id = multiplayer_routes.get_room_by_id
        self._original_start_room = multiplayer_commands.start_room
        self._original_close_room_for_host_disconnect = (
            multiplayer_host_timeout.close_room_for_host_disconnect
        )
        self._original_broadcast_room_event = multiplayer_host_timeout.broadcast_room_event
        self._original_has_host_connection = (
            multiplayer_routes.multiplayer_connection_manager.has_host_connection
        )
        self._original_reset_host_timeout = (
            multiplayer_routes.multiplayer_connection_manager.reset_host_timeout
        )
        self._original_websocket_require_user_context = (
            multiplayer_websocket.require_user_context
        )
        self._original_host_timeout_require_user_context = (
            multiplayer_host_timeout.require_user_context
        )

        multiplayer_websocket.authenticate_websocket = lambda token: {
            'uid': 'host-uid',
            'internal_user': {'id': 1},
        }
        multiplayer_websocket.SessionLocal = lambda: _DummySession()
        multiplayer_host_timeout.SessionLocal = lambda: _DummySession()
        room_snapshot = lambda db, room_id: {
            'id': room_id,
            'host_user_id': 1,
            'host_firebase_uid': 'host-uid',
            'status': 'waiting',
            'participants': [
                {
                    'user_id': 1,
                    'firebase_uid': 'host-uid',
                    'display_name': 'Host',
                    'score': 0,
                    'correct_answers': 0,
                    'answered_current_question': False,
                },
            ],
        }
        multiplayer_websocket.get_room_by_id = room_snapshot
        multiplayer_commands.get_room_by_id = room_snapshot
        multiplayer_host_timeout.get_room_by_id = room_snapshot
        multiplayer_routes.get_room_by_id = room_snapshot
        multiplayer_commands.start_room = lambda db, room_id, host_user_id: {
            'id': room_id,
            'status': 'in_progress',
            'current_question_index': 0,
            'participants': [
                {
                    'user_id': 1,
                    'firebase_uid': 'host-uid',
                    'display_name': 'Host',
                    'score': 0,
                    'correct_answers': 0,
                    'answered_current_question': False,
                },
            ],
        }

    def tearDown(self) -> None:
        multiplayer_websocket.authenticate_websocket = self._original_authenticate
        multiplayer_websocket.SessionLocal = self._original_websocket_session_local
        multiplayer_host_timeout.SessionLocal = self._original_host_timeout_session_local
        multiplayer_websocket.get_room_by_id = self._original_websocket_get_room_by_id
        multiplayer_commands.get_room_by_id = self._original_commands_get_room_by_id
        multiplayer_host_timeout.get_room_by_id = self._original_host_timeout_get_room_by_id
        multiplayer_routes.get_room_by_id = self._original_routes_get_room_by_id
        multiplayer_commands.start_room = self._original_start_room
        multiplayer_host_timeout.close_room_for_host_disconnect = (
            self._original_close_room_for_host_disconnect
        )
        multiplayer_host_timeout.broadcast_room_event = self._original_broadcast_room_event
        multiplayer_routes.multiplayer_connection_manager.has_host_connection = (
            self._original_has_host_connection
        )
        multiplayer_routes.multiplayer_connection_manager.reset_host_timeout = (
            self._original_reset_host_timeout
        )
        multiplayer_websocket.require_user_context = (
            self._original_websocket_require_user_context
        )
        multiplayer_host_timeout.require_user_context = (
            self._original_host_timeout_require_user_context
        )
        self.app.dependency_overrides.clear()
        self.client.close()

    def test_websocket_sends_initial_snapshot_and_replies_pong(self) -> None:
        with self.client.websocket_connect('/multiplayer/rooms/7/ws?token=test-token') as ws:
            initial = ws.receive_json()
            self.assertEqual(initial['event'], 'room.synced')
            self.assertEqual(initial['room_id'], 7)
            self.assertEqual(initial['room']['status'], 'waiting')

            ws.send_text('ping')
            pong = ws.receive_json()
            self.assertEqual(pong['event'], 'pong')
            self.assertEqual(pong['room_id'], 7)
            self.assertIn('server_time', pong)

    def test_websocket_executes_room_command_and_returns_result(self) -> None:
        with self.client.websocket_connect('/multiplayer/rooms/7/ws?token=test-token') as ws:
            ws.receive_json()

            ws.send_json(
                {
                    'type': 'command',
                    'request_id': 'req-1',
                    'action': 'start_match',
                    'payload': {},
                }
            )

            result = self._receive_until(ws, 'command.result')
            self.assertEqual(result['event'], 'command.result')
            self.assertEqual(result['request_id'], 'req-1')
            self.assertEqual(result['action'], 'start_match')
            self.assertEqual(result['result']['status'], 'in_progress')

    def test_host_offline_grace_period_is_sixty_seconds(self) -> None:
        self.assertEqual(multiplayer_routes.HOST_OFFLINE_GRACE_SECONDS, 60)

    def test_host_connection_resets_forced_timeout_on_connect_and_ping(self) -> None:
        resets = []

        def reset_host_timeout(room_id, *, delay_seconds, callback, force=False):
            resets.append((room_id, delay_seconds, force, callback))

        multiplayer_routes.multiplayer_connection_manager.reset_host_timeout = (
            reset_host_timeout
        )

        with self.client.websocket_connect('/multiplayer/rooms/7/ws?token=test-token') as ws:
            initial = ws.receive_json()
            self.assertEqual(initial['event'], 'room.synced')

            ws.send_text('ping')
            pong = ws.receive_json()
            self.assertEqual(pong['event'], 'pong')

        self.assertGreaterEqual(len(resets), 2)
        self.assertEqual(resets[0][0], 7)
        self.assertEqual(resets[0][1], multiplayer_routes.HOST_OFFLINE_GRACE_SECONDS)
        self.assertTrue(resets[0][2])

    def test_host_room_polling_resets_forced_timeout(self) -> None:
        resets = []

        def reset_host_timeout(room_id, *, delay_seconds, callback, force=False):
            resets.append((room_id, delay_seconds, force, callback))

        multiplayer_routes.multiplayer_connection_manager.reset_host_timeout = (
            reset_host_timeout
        )
        multiplayer_host_timeout.require_user_context = (
            lambda user_claims, require_firebase_uid=False: (1, 'host-uid')
        )
        self.app.dependency_overrides[multiplayer_routes.get_current_user] = lambda: {
            'uid': 'host-uid',
            'internal_user': {'id': 1},
        }

        response = self.client.get('/multiplayer/rooms/7')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(resets), 1)
        self.assertEqual(resets[0][0], 7)
        self.assertEqual(resets[0][1], multiplayer_routes.HOST_OFFLINE_GRACE_SECONDS)
        self.assertTrue(resets[0][2])

    def test_forced_host_timeout_closes_even_with_stale_connection(self) -> None:
        closed = []
        broadcasts = []

        multiplayer_routes.multiplayer_connection_manager.has_host_connection = (
            lambda room_id: True
        )

        def close_room(db, *, room_id, host_user_id):
            closed.append((room_id, host_user_id))
            return {
                'status': 'closed',
                'room_id': room_id,
                'reason': 'host_offline',
                'room': {
                    'id': room_id,
                    'status': 'closed',
                    'participants': [],
                },
            }

        async def broadcast(room_id, event_type, room_payload, *, data=None):
            broadcasts.append((room_id, event_type, room_payload, data))

        multiplayer_host_timeout.close_room_for_host_disconnect = close_room
        multiplayer_host_timeout.broadcast_room_event = broadcast

        asyncio.run(multiplayer_host_timeout.handle_host_offline_timeout(7, force=True))

        self.assertEqual(closed, [(7, 1)])
        self.assertEqual(broadcasts[0][1], multiplayer_routes.EVENT_ROOM_CLOSED)
        self.assertEqual(broadcasts[0][3], {'reason': 'host_offline'})

    def test_reset_host_timeout_invalidates_stale_task(self) -> None:
        async def scenario() -> None:
            manager = MultiplayerConnectionManager()
            calls = []

            async def callback(room_id: int, *, force: bool = False) -> None:
                calls.append((room_id, force))

            manager.reset_host_timeout(
                7,
                delay_seconds=0.05,
                callback=callback,
                force=True,
            )
            await asyncio.sleep(0.03)
            manager.reset_host_timeout(
                7,
                delay_seconds=0.05,
                callback=callback,
                force=True,
            )
            await asyncio.sleep(0.03)
            self.assertEqual(calls, [])
            await asyncio.sleep(0.04)
            self.assertEqual(calls, [(7, True)])

        asyncio.run(scenario())

    def _receive_until(self, ws, event_name: str) -> dict:
        for _ in range(5):
            payload = ws.receive_json()
            if payload.get('event') == event_name:
                return payload
        self.fail(f'Evento {event_name} nao recebido.')


if __name__ == '__main__':
    unittest.main()
