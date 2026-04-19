import unittest

from app.services.multiplayer import (
    EVENT_MATCH_STARTED,
    EVENT_ROOM_SYNCED,
    MULTIPLAYER_EVENT_TYPES,
    build_room_event,
)


class MultiplayerEventPayloadTests(unittest.TestCase):
    def test_catalog_keeps_expected_events(self) -> None:
        self.assertIn(EVENT_ROOM_SYNCED, MULTIPLAYER_EVENT_TYPES)
        self.assertIn(EVENT_MATCH_STARTED, MULTIPLAYER_EVENT_TYPES)

    def test_build_room_event_wraps_room_snapshot(self) -> None:
        payload = build_room_event(
            EVENT_ROOM_SYNCED,
            {'id': 7, 'status': 'waiting', 'participants': []},
            data={'source': 'polling'},
        )

        self.assertEqual(payload['event'], EVENT_ROOM_SYNCED)
        self.assertEqual(payload['room_id'], 7)
        self.assertEqual(payload['room']['status'], 'waiting')
        self.assertEqual(payload['data']['source'], 'polling')
        self.assertIn('server_time', payload)

    def test_build_room_event_rejects_unknown_event(self) -> None:
        with self.assertRaises(ValueError):
            build_room_event('room.unknown', {'id': 1})


if __name__ == '__main__':
    unittest.main()
