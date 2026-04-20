import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.models import metadata
from app.services.writing.service import analyze_writing
from app.services.writing.submissions import (
    count_writing_submissions,
    get_writing_submission_detail,
    list_writing_submissions,
    writing_submission_versions_table,
    writing_submissions_table,
)
from app.services.writing.themes import writing_themes_table


class WritingSubmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine('sqlite:///:memory:')
        self.themes_table = writing_themes_table()
        self.submissions_table = writing_submissions_table()
        self.versions_table = writing_submission_versions_table()
        metadata.create_all(
            self.engine,
            tables=[
                self.themes_table,
                self.submissions_table,
                self.versions_table,
            ],
        )
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.original_gemini_key = settings.gemini_api_key
        settings.gemini_api_key = 'test-key'

    def tearDown(self) -> None:
        settings.gemini_api_key = self.original_gemini_key
        self.db.close()
        metadata.drop_all(
            self.engine,
            tables=[
                self.versions_table,
                self.submissions_table,
                self.themes_table,
            ],
        )
        self.engine.dispose()

    def test_analyze_writing_creates_submission_and_first_version(self) -> None:
        with patch(
            'app.services.writing.service._generate_with_gemini',
            return_value=_mock_feedback(summary='Primeira versao'),
        ):
            result = analyze_writing(
                _mock_payload(),
                user_id=42,
                firebase_uid='firebase-42',
                db=self.db,
            )

        self.assertIsNotNone(result.get('submission_id'))
        self.assertEqual(result.get('version_number'), 1)
        self.assertEqual(count_writing_submissions(self.db, user_id=42), 1)

        submissions = list_writing_submissions(self.db, user_id=42)
        self.assertEqual(len(submissions), 1)
        self.assertEqual(submissions[0]['latest_summary'], 'Primeira versao')

        detail = get_writing_submission_detail(
            self.db,
            user_id=42,
            submission_id=result['submission_id'],
        )
        self.assertEqual(detail['current_version'], 1)
        self.assertEqual(len(detail['versions']), 1)
        self.assertEqual(detail['versions'][0]['summary'], 'Primeira versao')

    def test_reanalyze_same_submission_creates_new_version_only(self) -> None:
        with patch(
            'app.services.writing.service._generate_with_gemini',
            side_effect=[
                _mock_feedback(summary='Versao inicial', score=720),
                _mock_feedback(summary='Versao reescrita', score=860),
            ],
        ):
            first = analyze_writing(
                _mock_payload(),
                user_id=7,
                firebase_uid='firebase-7',
                db=self.db,
            )
            second = analyze_writing(
                _mock_payload(
                    submission_id=first['submission_id'],
                    final_text=(
                        'Texto final reescrito com ajustes mais profundos para '
                        'demonstrar a evolucao argumentativa e manter o minimo '
                        'de oitenta caracteres exigido no modulo. A nova versao '
                        'tambem apresenta exemplos concretos, conecta melhor as '
                        'ideias e reforca a proposta de intervencao com agentes, '
                        'meios e finalidade social.'
                    ),
                ),
                user_id=7,
                firebase_uid='firebase-7',
                db=self.db,
            )

        self.assertEqual(first['submission_id'], second['submission_id'])
        self.assertEqual(first['version_number'], 1)
        self.assertEqual(second['version_number'], 2)
        self.assertEqual(count_writing_submissions(self.db, user_id=7), 1)

        detail = get_writing_submission_detail(
            self.db,
            user_id=7,
            submission_id=second['submission_id'],
        )
        self.assertEqual(detail['current_version'], 2)
        self.assertEqual(detail['latest_score'], 860)
        self.assertEqual(len(detail['versions']), 2)
        self.assertEqual(detail['versions'][0]['version_number'], 2)
        self.assertEqual(detail['versions'][0]['summary'], 'Versao reescrita')
        self.assertEqual(detail['versions'][1]['version_number'], 1)

        first_page = get_writing_submission_detail(
            self.db,
            user_id=7,
            submission_id=second['submission_id'],
            versions_limit=1,
            versions_offset=0,
        )
        self.assertEqual(first_page['versions_total'], 2)
        self.assertTrue(first_page['versions_has_more'])
        self.assertEqual(len(first_page['versions']), 1)
        self.assertEqual(first_page['versions'][0]['version_number'], 2)

        second_page = get_writing_submission_detail(
            self.db,
            user_id=7,
            submission_id=second['submission_id'],
            versions_limit=1,
            versions_offset=1,
        )
        self.assertFalse(second_page['versions_has_more'])
        self.assertEqual(len(second_page['versions']), 1)
        self.assertEqual(second_page['versions'][0]['version_number'], 1)

    def test_reanalyze_same_theme_reuses_existing_submission(self) -> None:
        with patch(
            'app.services.writing.service._generate_with_gemini',
            side_effect=[
                _mock_feedback(summary='Primeira analise', score=650),
                _mock_feedback(summary='Segunda analise', score=750),
            ],
        ):
            first = analyze_writing(
                _mock_payload(),
                user_id=8,
                firebase_uid='firebase-8',
                db=self.db,
            )
            second = analyze_writing(
                _mock_payload(
                    final_text=(
                        'A empatia fortalece a convivencia social quando '
                        'instituicoes educacionais promovem dialogo, respeito '
                        'e escuta ativa entre grupos diversos. Com isso, a '
                        'sociedade reduz conflitos, combate intolerancias e '
                        'desenvolve formas mais cooperativas de participacao '
                        'civica, especialmente em ambientes marcados por '
                        'desigualdade e polarizacao.'
                    ),
                ),
                user_id=8,
                firebase_uid='firebase-8',
                db=self.db,
            )

        self.assertEqual(first['submission_id'], second['submission_id'])
        self.assertEqual(second['version_number'], 2)
        self.assertEqual(count_writing_submissions(self.db, user_id=8), 1)

        submissions = list_writing_submissions(self.db, user_id=8)
        self.assertEqual(len(submissions), 1)
        self.assertEqual(submissions[0]['current_version'], 2)
        self.assertEqual(submissions[0]['latest_score'], 750)
        self.assertEqual(submissions[0]['latest_summary'], 'Segunda analise')

    def test_analyze_writing_rejects_gibberish_text(self) -> None:
        with patch('app.services.writing.service._generate_with_gemini') as gemini:
            with self.assertRaises(HTTPException) as context:
                analyze_writing(
                    _mock_payload(
                        final_text=(
                            '123123 ddddddddddddddddddddddddddddddddddddd '
                            '123123 ddddddddddddddddddddddddddddddddddddd '
                            '123123 ddddddddddddddddddddddddddddddddddddd '
                            '123123 ddddddddddddddddddddddddddddddddddddd'
                        ),
                    ),
                    user_id=99,
                    firebase_uid='firebase-99',
                    db=self.db,
                )

        self.assertEqual(context.exception.status_code, 422)
        gemini.assert_not_called()

    def test_analyze_writing_rejects_technical_noise_text(self) -> None:
        with patch('app.services.writing.service._generate_with_gemini') as gemini:
            with self.assertRaises(HTTPException) as context:
                analyze_writing(
                    _mock_payload(
                        final_text=(
                            'ol tenho teste de fase de vi composta '
                            '6666666666666666666666666666666666666666 '
                            'C:\\Users\\Nogueira\\Desktop\\cognix\\lib\\widgets'
                            '\\cognix\\cognix_messages.dart 555555555555555555 '
                            'C:\\Users\\Nogueira\\Desktop\\cognix\\lib\\widgets'
                            '\\cognix\\cognix_messages.dart '
                            'ol, iniciando historia 555555555555555555550000000000'
                        ),
                    ),
                    user_id=100,
                    firebase_uid='firebase-100',
                    db=self.db,
                )

        self.assertEqual(context.exception.status_code, 422)
        gemini.assert_not_called()

    def test_analyze_writing_rejects_common_troll_patterns(self) -> None:
        invalid_texts = [
            (
                'A sociedade precisa melhorar a educacao e o respeito coletivo. '
                'Veja mais em https://spam.example.com e mande email para '
                'teste@exemplo.com porque esse texto nao e uma redacao real.'
            ),
            (
                'A sociedade precisa discutir esse tema com seriedade. '
                'function teste() { return true; }; import algumaCoisa from app; '
                'class FakeText cria codigo em vez de argumento dissertativo.'
            ),
            (
                'lorem ipsum lorem ipsum texto teste qualquer coisa para encher '
                'linguica e fingir que existe uma redacao com desenvolvimento, '
                'mas sem tese real, sem argumento e sem proposta consistente.'
            ),
            (
                'qwerty asdf zxcv kkkkk hahaha hahaha rsrsrs isso aqui tenta '
                'passar como texto, mas nao desenvolve uma tese, nao organiza '
                'argumentos e nao apresenta uma proposta de intervencao real.'
            ),
            (
                'A educacao deve ser fortalecida por politicas publicas.\n'
                'A educacao deve ser fortalecida por politicas publicas.\n'
                'A educacao deve ser fortalecida por politicas publicas.\n'
                'A educacao deve ser fortalecida por politicas publicas.\n'
                'A educacao deve ser fortalecida por politicas publicas.'
            ),
            (
                'anticonstitucionalissimamentefakeeeeeeeeeeeeeeeeeeeeeeee '
                'A sociedade precisa discutir o problema, mas este texto usa '
                'palavras artificiais gigantes para tentar enganar a validacao.'
            ),
        ]

        for invalid_text in invalid_texts:
            with self.subTest(invalid_text=invalid_text[:24]):
                with patch('app.services.writing.service._generate_with_gemini') as gemini:
                    with self.assertRaises(HTTPException) as context:
                        analyze_writing(
                            _mock_payload(final_text=invalid_text),
                            user_id=101,
                            firebase_uid='firebase-101',
                            db=self.db,
                        )

                self.assertEqual(context.exception.status_code, 422)
                gemini.assert_not_called()


def _mock_payload(
    *,
    submission_id: int | None = None,
    final_text: str = (
        'A empatia fortalece a convivencia social ao reduzir conflitos e ampliar '
        'a capacidade de dialogo entre diferentes grupos da sociedade. Quando '
        'as pessoas reconhecem necessidades, limites e experiencias alheias, '
        'elas constroem relacoes mais respeitosas, cooperativas e preparadas '
        'para resolver conflitos sem violencia.'
    ),
) -> dict:
    payload = {
        'theme': {
            'id': 'empatia-social',
            'title': 'A importancia da empatia',
            'category': 'Cidadania',
            'description': 'Tema sobre empatia e convivencia.',
            'keywords': ['empatia', 'convivencia'],
        },
        'thesis': 'A empatia e essencial para fortalecer a convivencia social.',
        'repertoire': 'Bauman discute a fragilidade das relacoes contemporaneas.',
        'argument_one': 'Sem empatia, o convivio cotidiano fica mais intolerante.',
        'argument_two': 'A escuta ativa melhora cooperacao e respeito mutuo.',
        'intervention': (
            'Portanto, escolas e midias devem promover campanhas e projetos '
            'de educacao socioemocional para estimular o respeito.'
        ),
        'final_text': final_text,
    }
    if submission_id is not None:
        payload['submission_id'] = submission_id
    return payload


def _mock_feedback(*, summary: str, score: int = 850) -> dict:
    return {
        'estimated_score': score,
        'summary': summary,
        'checklist': [
            {
                'label': 'Tese clara',
                'completed': True,
                'helper': 'Apresente uma posicao objetiva.',
            },
        ],
        'competencies': [
            {
                'title': 'Competencia 1',
                'score': 160,
                'comment': 'Boa adequacao linguistica.',
            },
        ],
        'rewrite_suggestions': [
            {
                'section': 'Conclusao',
                'issue': 'Falta detalhamento.',
                'suggestion': 'Amplie a proposta de intervencao.',
                'example': 'Inclua meios concretos de execucao.',
            },
        ],
    }


if __name__ == '__main__':
    unittest.main()
