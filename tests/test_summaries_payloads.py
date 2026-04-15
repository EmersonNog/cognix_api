import unittest

from fastapi import HTTPException

from app.services.summaries.payloads import load_summary_payload


class SummariesPayloadsTests(unittest.TestCase):
    def test_load_summary_payload_accepts_json_string(self) -> None:
        payload = load_summary_payload(
            '{"title":"Algebra","discipline":"Matematica","subcategory":"Algebra","nodes":[{"title":"Conceitos","items":["Equacoes"]}]}'
        )

        self.assertEqual(payload['title'], 'Algebra')
        self.assertEqual(payload['nodes'][0]['title'], 'Conceitos')

    def test_load_summary_payload_accepts_dict_from_jsonb(self) -> None:
        payload = load_summary_payload(
            {
                'title': 'Algebra',
                'discipline': 'Matematica',
                'subcategory': 'Algebra',
                'nodes': [
                    {
                        'title': 'Conceitos',
                        'items': ['Equacoes'],
                    }
                ],
            }
        )

        self.assertEqual(payload['discipline'], 'Matematica')
        self.assertEqual(payload['subcategory'], 'Algebra')

    def test_load_summary_payload_rejects_invalid_json(self) -> None:
        with self.assertRaises(HTTPException):
            load_summary_payload('{invalid')


if __name__ == '__main__':
    unittest.main()
