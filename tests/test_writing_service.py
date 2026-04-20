import unittest

from app.services.writing.normalize import normalize_writing_feedback


class WritingServiceTests(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
