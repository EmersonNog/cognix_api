import unittest
from base64 import b64encode
from unittest.mock import patch

from fastapi import HTTPException

from app.core.config import settings
from app.services.writing.image_scan import scan_writing_image
from app.services.writing.normalize import normalize_writing_feedback
from app.services.writing.prompt import build_writing_prompt
from app.services.writing.schemas import (
    build_writing_feedback_schema,
    build_writing_image_scan_schema,
)


class WritingServiceTests(unittest.TestCase):
    def test_gemini_response_schemas_are_top_level_objects(self) -> None:
        feedback_schema = build_writing_feedback_schema()
        image_scan_schema = build_writing_image_scan_schema()

        self.assertIsInstance(feedback_schema, dict)
        self.assertEqual(feedback_schema.get('type'), 'object')
        self.assertIn('estimated_score', feedback_schema.get('properties', {}))
        self.assertIn('rewrite_suggestions', feedback_schema.get('properties', {}))

        self.assertIsInstance(image_scan_schema, dict)
        self.assertEqual(image_scan_schema.get('type'), 'object')
        self.assertIn('text', image_scan_schema.get('properties', {}))
        self.assertIn('confidence', image_scan_schema.get('properties', {}))

    def test_writing_prompt_penalizes_theme_mismatch(self) -> None:
        prompt = build_writing_prompt(
            {
                'theme': {
                    'id': 'mobilidade-urbana',
                    'title': 'Desafios da mobilidade urbana no Brasil',
                    'category': 'Cidadania',
                    'description': 'Discuta transporte publico e acessibilidade.',
                    'keywords': ['transporte', 'acessibilidade'],
                },
                'final_text': 'Texto sobre outro tema.',
            },
            user_id=7,
        )

        self.assertIn('Aderência ao tema é critério central', prompt)
        self.assertIn('fuga ao tema', prompt)
        self.assertIn('estimated_score deve ser no máximo 320', prompt)
        self.assertIn('tangenciar o tema', prompt)
        self.assertIn('Tema: Desafios da mobilidade urbana no Brasil', prompt)

    def test_normalize_writing_feedback_clamps_scores_and_limits_lists(self) -> None:
        payload = {
            'estimated_score': 1200,
            'summary': ' Boa base. ',
            'checklist': [
                {'label': 'Tese', 'completed': True, 'helper': 'ok'},
                {'label': 'Extra', 'completed': False, 'helper': 'x'},
                {'label': 'Extra', 'completed': False, 'helper': 'x'},
                {'label': 'Extra', 'completed': False, 'helper': 'x'},
                {'label': 'Extra', 'completed': False, 'helper': 'x'},
                {'label': 'Extra', 'completed': False, 'helper': 'x'},
            ],
            'competencies': [
                {'title': 'Competência 1', 'score': 250, 'comment': 'alta'},
            ],
            'rewrite_suggestions': [
                {
                    'section': 'Tese',
                    'issue': 'pouco clara',
                    'suggestion': 'declare sua posição',
                    'example': 'Logo, ...',
                },
            ],
        }

        result = normalize_writing_feedback(payload)

        self.assertEqual(result['estimated_score'], 1000)
        self.assertEqual(result['summary'], 'Boa base.')
        self.assertEqual(len(result['checklist']), 5)
        self.assertEqual(result['competencies'][0]['score'], 200)
        self.assertTrue(result['checklist'][0]['completed'])

    def test_normalize_writing_feedback_handles_invalid_shapes(self) -> None:
        result = normalize_writing_feedback(
            {
                'estimated_score': 'invalid',
                'summary': None,
                'checklist': 'invalid',
                'competencies': 'invalid',
                'rewrite_suggestions': 'invalid',
            }
        )

        self.assertEqual(result['estimated_score'], 0)
        self.assertEqual(result['summary'], '')
        self.assertEqual(result['checklist'], [])
        self.assertEqual(result['competencies'], [])
        self.assertEqual(result['rewrite_suggestions'], [])

    def test_scan_writing_image_uses_gemini_image_payload(self) -> None:
        original_key = settings.gemini_api_key
        settings.gemini_api_key = 'test-key'
        try:
            with patch(
                'app.services.writing.image_scan._generate_image_scan_with_gemini',
                return_value={
                    'text': 'Texto transcrito',
                    'confidence': 0.82,
                    'warnings': ['foto escura'],
                },
            ) as gemini:
                result = scan_writing_image(
                    {
                        'image_base64': b64encode(b'image-bytes').decode('ascii'),
                        'mime_type': 'image/jpeg',
                    },
                    user_id=7,
                )

            self.assertEqual(result['text'], 'Texto transcrito')
            self.assertEqual(result['confidence'], 0.82)
            self.assertEqual(result['warnings'], ['foto escura'])
            _, kwargs = gemini.call_args
            self.assertEqual(kwargs['image_bytes'], b'image-bytes')
            self.assertEqual(kwargs['mime_type'], 'image/jpeg') 
            self.assertIn('Usuário interno: 7', kwargs['prompt'])
        finally:
            settings.gemini_api_key = original_key

    def test_scan_writing_image_rejects_invalid_mime_type(self) -> None:
        original_key = settings.gemini_api_key
        settings.gemini_api_key = 'test-key'
        try:
            with self.assertRaises(HTTPException) as error:
                scan_writing_image(
                    {
                        'image_base64': b64encode(b'image-bytes').decode('ascii'),
                        'mime_type': 'text/plain',
                    },
                    user_id=7,
                )

            self.assertEqual(error.exception.status_code, 422)
        finally:
            settings.gemini_api_key = original_key


if __name__ == '__main__':
    unittest.main()
