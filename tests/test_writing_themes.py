import unittest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.datetime_utils import utc_now
from app.db.models import metadata
from app.services.writing.themes import (
    count_writing_themes,
    get_monthly_writing_theme,
    list_writing_categories,
    list_writing_themes,
    writing_themes_table,
)


class WritingThemeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine('sqlite:///:memory:')
        self.table = writing_themes_table()
        metadata.create_all(self.engine, tables=[self.table])
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        now = utc_now()
        self.db.execute(
            self.table.insert(),
            [
                {
                    'slug': 'digital-education',
                    'titulo': 'Inclusao digital',
                    'categoria': 'Educacao',
                    'descricao': 'Tema de educacao.',
                    'palavras_chave_json': '["educacao","internet"]',
                    'dificuldade': 'medio',
                    'prova': 'ENEM',
                    'ativo': True,
                    'redacao_do_mes': True,
                    'created_at': now,
                    'updated_at': now,
                },
                {
                    'slug': 'food-insecurity',
                    'titulo': 'Inseguranca alimentar',
                    'categoria': 'Cidadania',
                    'descricao': 'Tema de cidadania.',
                    'palavras_chave_json': '["fome","renda"]',
                    'dificuldade': 'medio',
                    'prova': 'ENEM',
                    'ativo': True,
                    'redacao_do_mes': False,
                    'created_at': now,
                    'updated_at': now,
                },
            ],
        )
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        metadata.drop_all(self.engine, tables=[self.table])
        self.engine.dispose()

    def test_list_writing_themes_can_filter_by_category(self) -> None:
        themes = list_writing_themes(self.db, category='Cidadania')

        self.assertTrue(themes)
        self.assertTrue(all(theme['category'] == 'Cidadania' for theme in themes))

    def test_list_writing_themes_can_paginate_results(self) -> None:
        themes = list_writing_themes(self.db, limit=1, offset=0)

        self.assertEqual(len(themes), 1)
        self.assertEqual(count_writing_themes(self.db), 2)

    def test_list_writing_themes_can_search_results(self) -> None:
        themes = list_writing_themes(self.db, search='fome')

        self.assertEqual(len(themes), 1)
        self.assertEqual(themes[0]['id'], 'food-insecurity')

    def test_list_writing_categories_returns_sorted_unique_values(self) -> None:
        categories = list_writing_categories(self.db)

        self.assertEqual(categories, sorted(categories))
        self.assertEqual(len(categories), len(set(categories)))
        self.assertIn('Educacao', categories)

    def test_monthly_writing_theme_prefers_database_monthly_flag(self) -> None:
        monthly = get_monthly_writing_theme(self.db, today=date(2026, 4, 19))

        self.assertEqual(monthly['id'], 'digital-education')

    def test_monthly_writing_theme_returns_empty_when_table_is_empty(self) -> None:
        self.db.execute(self.table.delete())
        self.db.commit()

        self.assertEqual(get_monthly_writing_theme(self.db), {})


if __name__ == '__main__':
    unittest.main()
