import unittest
from unittest.mock import Mock, patch

from app.services.recommendations.service import fetch_home_recommendations


class HomeRecommendationsTests(unittest.TestCase):
    @patch('app.services.recommendations.service.fetch_question_total')
    @patch('app.services.recommendations.service._fetch_subcategory_candidates')
    @patch('app.services.recommendations.service.fetch_study_plan_row')
    @patch('app.services.recommendations.service.fetch_profile_metrics')
    def test_recommendations_prioritize_weakest_then_plan_disciplines(
        self,
        fetch_profile_metrics_mock,
        fetch_study_plan_row_mock,
        fetch_subcategory_candidates_mock,
        fetch_question_total_mock,
    ) -> None:
        fetch_profile_metrics_mock.return_value = {
            'weakest_subcategory': {
                'discipline': 'Matematica e suas Tecnologias',
                'subcategory': 'Geometria Espacial',
                'accuracy_percent': 42.0,
                'total_attempts': 6,
            }
        }
        fetch_study_plan_row_mock.return_value = {
            'priority_disciplines_json': '["Matematica e suas Tecnologias", "Ciencias Humanas e suas Tecnologias"]'
        }
        fetch_question_total_mock.return_value = 14
        fetch_subcategory_candidates_mock.side_effect = [
            [
                {
                    'discipline': 'Matematica e suas Tecnologias',
                    'subcategory': 'Analise Combinatoria',
                    'total_questions': 11,
                    'total_attempts': 0,
                    'accuracy_percent': None,
                }
            ],
            [
                {
                    'discipline': 'Ciencias Humanas e suas Tecnologias',
                    'subcategory': 'Geopolitica',
                    'total_questions': 9,
                    'total_attempts': 2,
                    'accuracy_percent': 55.0,
                }
            ],
            [],
        ]

        payload = fetch_home_recommendations(Mock(), user_id=7)

        self.assertEqual(
            [item['subcategory'] for item in payload['items'][:3]],
            [
                'Geometria Espacial',
                'Analise Combinatoria',
                'Geopolitica',
            ],
        )
        self.assertEqual(payload['items'][0]['badge_label'], 'Critico')
        self.assertEqual(payload['items'][1]['reason_label'], 'Sem cobertura recente')
        self.assertEqual(
            payload['subtitle'],
            'Priorizando pontos de atencao e frentes do seu plano',
        )

    @patch('app.services.recommendations.service._fetch_subcategory_candidates')
    @patch('app.services.recommendations.service.fetch_study_plan_row')
    @patch('app.services.recommendations.service.fetch_profile_metrics')
    def test_recommendations_fall_back_to_global_coverage_when_needed(
        self,
        fetch_profile_metrics_mock,
        fetch_study_plan_row_mock,
        fetch_subcategory_candidates_mock,
    ) -> None:
        fetch_profile_metrics_mock.return_value = {
            'weakest_subcategory': None,
        }
        fetch_study_plan_row_mock.return_value = None
        fetch_subcategory_candidates_mock.return_value = [
            {
                'discipline': 'Linguagens, Codigos e suas Tecnologias',
                'subcategory': 'Gramatica',
                'total_questions': 18,
                'total_attempts': 0,
                'accuracy_percent': None,
            },
            {
                'discipline': 'Matematica e suas Tecnologias',
                'subcategory': 'Funcoes',
                'total_questions': 15,
                'total_attempts': 0,
                'accuracy_percent': None,
            },
        ]

        payload = fetch_home_recommendations(Mock(), user_id=9)

        self.assertEqual(len(payload['items']), 2)
        self.assertEqual(payload['items'][0]['source'], 'coverage_gap')
        self.assertEqual(
            payload['subtitle'],
            'Priorizando disciplinas para ampliar cobertura hoje',
        )

    @patch('app.services.recommendations.service.fetch_question_total')
    @patch('app.services.recommendations.service._fetch_subcategory_candidates')
    @patch('app.services.recommendations.service.fetch_study_plan_row')
    @patch('app.services.recommendations.service.fetch_profile_metrics')
    def test_recommendations_skip_priority_duplicates_of_weakest(
        self,
        fetch_profile_metrics_mock,
        fetch_study_plan_row_mock,
        fetch_subcategory_candidates_mock,
        fetch_question_total_mock,
    ) -> None:
        fetch_profile_metrics_mock.return_value = {
            'weakest_subcategory': {
                'discipline': 'Matematica e suas Tecnologias',
                'subcategory': 'Probabilidade',
                'accuracy_percent': 38.0,
                'total_attempts': 5,
            }
        }
        fetch_study_plan_row_mock.return_value = {
            'priority_disciplines_json': '["Matematica e suas Tecnologias"]'
        }
        fetch_question_total_mock.return_value = 10
        fetch_subcategory_candidates_mock.side_effect = [
            [
                {
                    'discipline': 'Matematica e suas Tecnologias',
                    'subcategory': 'Probabilidade',
                    'total_questions': 10,
                    'total_attempts': 5,
                    'accuracy_percent': 38.0,
                },
                {
                    'discipline': 'Matematica e suas Tecnologias',
                    'subcategory': 'Funcoes',
                    'total_questions': 16,
                    'total_attempts': 0,
                    'accuracy_percent': None,
                },
            ],
            [],
        ]

        payload = fetch_home_recommendations(Mock(), user_id=11)

        self.assertEqual(
            [item['subcategory'] for item in payload['items']],
            ['Probabilidade', 'Funcoes'],
        )


if __name__ == '__main__':
    unittest.main()
