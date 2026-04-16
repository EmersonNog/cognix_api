import unittest

from fastapi import HTTPException

from app.services.question_reports import (
    normalize_optional_report_text,
    normalize_question_report_reason,
    normalize_question_report_reasons,
    parse_question_report_payload,
)


class QuestionReportPayloadTests(unittest.TestCase):
    def test_questions_endpoint_module_imports_report_route(self) -> None:
        from app.api.endpoints import questions

        self.assertTrue(hasattr(questions, 'report_question'))

    def test_parse_question_report_payload_normalizes_values(self) -> None:
        payload = parse_question_report_payload(
            {
                'reasons': ['missing_image', 'broken_image'],
                'details': '  Imagem nao aparece no enunciado.  ',
                'discipline': '  Matematica  ',
                'subcategory': '  Algebra  ',
            }
        )

        self.assertEqual(payload['reason'], 'missing_image,broken_image')
        self.assertEqual(payload['reasons'], ['missing_image', 'broken_image'])
        self.assertEqual(payload['details'], 'Imagem nao aparece no enunciado.')
        self.assertEqual(payload['discipline'], 'Matematica')
        self.assertEqual(payload['subcategory'], 'Algebra')

    def test_parse_question_report_payload_accepts_legacy_single_reason(self) -> None:
        payload = parse_question_report_payload({'reason': 'missing_image'})

        self.assertEqual(payload['reason'], 'missing_image')
        self.assertEqual(payload['reasons'], ['missing_image'])

    def test_normalize_question_report_reason_rejects_unknown_reason(self) -> None:
        with self.assertRaises(HTTPException) as error:
            normalize_question_report_reason('invalid_reason')

        self.assertEqual(error.exception.status_code, 400)

    def test_normalize_question_report_reasons_deduplicates_values(self) -> None:
        reasons = normalize_question_report_reasons(
            {'reasons': ['missing_image', 'missing_image', 'broken_image']}
        )

        self.assertEqual(reasons, ['missing_image', 'broken_image'])

    def test_parse_question_report_payload_requires_details_for_other(self) -> None:
        with self.assertRaises(HTTPException) as error:
            parse_question_report_payload({'reasons': ['other']})

        self.assertEqual(error.exception.status_code, 400)

    def test_parse_question_report_payload_rejects_other_with_another_reason(self) -> None:
        with self.assertRaises(HTTPException) as error:
            parse_question_report_payload(
                {'reasons': ['other', 'missing_statement'], 'details': 'Outro'}
            )

        self.assertEqual(error.exception.status_code, 400)

    def test_parse_question_report_payload_accepts_other_with_details(self) -> None:
        payload = parse_question_report_payload(
            {'reasons': ['other'], 'details': 'Texto duplicado na questao.'}
        )

        self.assertEqual(payload['reason'], 'other')
        self.assertEqual(payload['details'], 'Texto duplicado na questao.')

    def test_parse_question_report_payload_requires_reason(self) -> None:
        with self.assertRaises(HTTPException) as error:
            parse_question_report_payload({})

        self.assertEqual(error.exception.status_code, 400)

    def test_normalize_optional_report_text_rejects_long_value(self) -> None:
        with self.assertRaises(HTTPException) as error:
            normalize_optional_report_text('details', 'x' * 4, max_length=3)

        self.assertEqual(error.exception.status_code, 400)


if __name__ == '__main__':
    unittest.main()
