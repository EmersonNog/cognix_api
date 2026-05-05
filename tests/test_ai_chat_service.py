import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.core.config import settings
from app.services.ai_chat.prompt import build_gemini_chat_prompt
from app.services.ai_chat.service import generate_ai_chat_reply
from app.services.ai_chat.validation import normalize_chat_messages


class AiChatServiceTests(unittest.TestCase):
    def test_normalize_chat_messages_requires_user_message_at_end(self) -> None:
        with self.assertRaises(HTTPException) as error:
            normalize_chat_messages(
                [
                    {'role': 'user', 'content': 'Explique fotossintese'},
                    {'role': 'assistant', 'content': 'Claro.'},
                ]
            )

        self.assertEqual(error.exception.status_code, 422)

    def test_normalize_chat_messages_limits_history_and_content(self) -> None:
        original_max_messages = settings.ai_chat_max_messages
        original_max_content_chars = settings.ai_chat_max_content_chars
        settings.ai_chat_max_messages = 2
        settings.ai_chat_max_content_chars = 4
        try:
            messages = normalize_chat_messages(
                [
                    {'role': 'user', 'content': 'primeira'},
                    {'role': 'assistant', 'content': 'segunda'},
                    {'role': 'user', 'content': 'terceira'},
                ]
            )
        finally:
            settings.ai_chat_max_messages = original_max_messages
            settings.ai_chat_max_content_chars = original_max_content_chars

        self.assertEqual(
            messages,
            [
                {'role': 'assistant', 'content': 'segu'},
                {'role': 'user', 'content': 'terc'},
            ],
        )

    def test_build_gemini_chat_prompt_keeps_recent_context(self) -> None:
        prompt = build_gemini_chat_prompt(
            [
                {'role': 'assistant', 'content': 'Vamos revisar.'},
                {'role': 'user', 'content': 'Explique mitose.'},
            ],
            user_id=42,
        )

        self.assertIn('Usuario interno: 42', prompt)
        self.assertIn('Cognix: Vamos revisar.', prompt)
        self.assertIn('Aluno: Explique mitose.', prompt)

    def test_build_gemini_chat_prompt_marks_previous_user_question(self) -> None:
        prompt = build_gemini_chat_prompt(
            [
                {
                    'role': 'user',
                    'content': 'Tenho uma dúvida sobre metáforas.',
                },
                {
                    'role': 'assistant',
                    'content': 'Claro, vamos por partes.',
                },
                {
                    'role': 'user',
                    'content': 'Qual foi minha última pergunta?',
                },
            ],
            user_id=42,
        )

        self.assertIn(
            'Pergunta anterior do aluno: Tenho uma dúvida sobre metáforas.',
            prompt,
        )
        self.assertIn('Mensagem atual do aluno:', prompt)
        self.assertIn('nao a propria mensagem atual', prompt)

    def test_generate_ai_chat_reply_uses_gemini_completion(self) -> None:
        original_key = settings.gemini_api_key
        settings.gemini_api_key = 'test-key'
        try:
            with patch(
                'app.services.ai_chat.service._generate_with_gemini',
                return_value='Revise por blocos curtos.',
            ) as completion:
                result = generate_ai_chat_reply(
                    {
                        'messages': [
                            {
                                'role': 'user',
                                'content': 'Monte um plano para hoje',
                            }
                        ]
                    },
                    user_id=42,
                )
        finally:
            settings.gemini_api_key = original_key

        self.assertEqual(result['message']['role'], 'assistant')
        self.assertEqual(result['message']['content'], 'Revise por blocos curtos.')
        self.assertEqual(result['model'], settings.gemini_model)
        sent_prompt = completion.call_args.args[0]
        self.assertIn('Usuario interno: 42', sent_prompt)
        self.assertIn('Aluno: Monte um plano para hoje', sent_prompt)

    def test_generate_ai_chat_reply_requires_gemini_key(self) -> None:
        original_key = settings.gemini_api_key
        settings.gemini_api_key = None
        try:
            with self.assertRaises(HTTPException) as error:
                generate_ai_chat_reply(
                    {'messages': [{'role': 'user', 'content': 'Oi'}]},
                    user_id=42,
                )
        finally:
            settings.gemini_api_key = original_key

        self.assertEqual(error.exception.status_code, 503)


if __name__ == '__main__':
    unittest.main()
