import unittest

from fastapi import HTTPException

from app.services.multiplayer.payloads import (
    normalize_display_name,
    normalize_pin,
    parse_answer_payload,
    parse_create_room_payload,
    parse_join_room_payload,
    parse_max_participants,
)


class MultiplayerPayloadTests(unittest.TestCase):
    def test_normalize_pin_accepts_six_digits(self) -> None:
        self.assertEqual(normalize_pin(' 123456 '), '123456')

    def test_normalize_pin_rejects_invalid_values(self) -> None:
        for value in ('12345', '1234567', 'abc123', ''):
            with self.subTest(value=value):
                with self.assertRaises(HTTPException):
                    normalize_pin(value)

    def test_parse_max_participants_defaults_to_eight(self) -> None:
        self.assertEqual(parse_max_participants(None), 8)

    def test_parse_max_participants_rejects_out_of_range_values(self) -> None:
        for value in (1, 9):
            with self.subTest(value=value):
                with self.assertRaises(HTTPException):
                    parse_max_participants(value)

    def test_normalize_display_name_trims_and_limits_value(self) -> None:
        self.assertEqual(normalize_display_name('  Ana  '), 'Ana')
        self.assertEqual(len(normalize_display_name('x' * 300)), 255)

    def test_parse_create_room_payload(self) -> None:
        payload = parse_create_room_payload(
            {'display_name': 'Host', 'max_participants': '4'}
        )

        self.assertEqual(payload['display_name'], 'Host')
        self.assertEqual(payload['max_participants'], 4)

    def test_parse_join_room_payload(self) -> None:
        payload = parse_join_room_payload(
            {'pin': '654321', 'display_name': 'Jogador'}
        )

        self.assertEqual(payload['pin'], '654321')
        self.assertEqual(payload['display_name'], 'Jogador')

    def test_parse_answer_payload_normalizes_values(self) -> None:
        payload = parse_answer_payload(
            {'question_id': '42', 'selected_letter': ' b '}
        )

        self.assertEqual(payload['question_id'], 42)
        self.assertEqual(payload['selected_letter'], 'B')

    def test_parse_answer_payload_rejects_invalid_values(self) -> None:
        for payload in (
            {'question_id': 'x', 'selected_letter': 'A'},
            {'question_id': 0, 'selected_letter': 'A'},
            {'question_id': 42, 'selected_letter': ''},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(HTTPException):
                    parse_answer_payload(payload)

    def test_multiplayer_endpoint_module_imports_routes(self) -> None:
        from app.api.endpoints import multiplayer

        self.assertTrue(hasattr(multiplayer, 'router'))


if __name__ == '__main__':
    unittest.main()
