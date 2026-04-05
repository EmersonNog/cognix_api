import json
import urllib.error
import urllib.request

from fastapi import HTTPException

from app.core.config import settings
from .payloads import normalize_summary_payload
from .stats import fetch_question_samples, fetch_user_stats


def gemini_available() -> bool:
    return bool(settings.gemini_api_key and settings.gemini_api_key.strip())


def build_schema() -> dict:
    return {
        'type': 'object',
        'properties': {
            'title': {'type': 'string'},
            'discipline': {'type': 'string'},
            'subcategory': {'type': 'string'},
            'nodes': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'title': {'type': 'string'},
                        'items': {'type': 'array', 'items': {'type': 'string'}},
                    },
                    'required': ['title', 'items'],
                    'additionalProperties': False,
                },
            },
        },
        'required': ['title', 'discipline', 'subcategory', 'nodes'],
        'additionalProperties': False,
    }


def generate_personalized_summary(
    db,
    user_id: int,
    discipline: str,
    subcategory: str,
) -> tuple[dict, dict]:
    stats = fetch_user_stats(db, user_id, discipline, subcategory)
    samples = fetch_question_samples(db, discipline, subcategory)
    payload = normalize_summary_payload(
        generate_with_gemini(discipline, subcategory, samples, stats)
    )
    return payload, stats


def generate_with_gemini(
    discipline: str,
    subcategory: str,
    samples: list[dict],
    stats: dict,
) -> dict:
    prompt = (
        'Crie um mapa mental em JSON para estudo. '
        'Use linguagem clara, objetiva e util para revisao. '
        'O conteudo precisa cobrir os pontos mais importantes da disciplina, '
        'sem ficar superficial, mas mantendo formato enxuto para mobile. '
        'Inclua de 4 a 5 nos principais, cada um com no maximo 3 itens. '
        'Cada no deve representar um bloco realmente importante do tema. '
        'Cada item deve ser curto, especifico, relevante para prova e revisao, '
        'e idealmente caber em uma frase breve sem precisar de reticencias. '
        'Personalize com foco no desempenho real do aluno usando os dados informados.\n\n'
        'Priorize nesta ordem:\n'
        '1. conceitos centrais da disciplina;\n'
        '2. formulas, relacoes ou interpretacoes essenciais;\n'
        '3. pontos de confusao e fragilidades sugeridos pelo desempenho;\n'
        '4. aplicacoes ou leituras que mais costumam aparecer nas questoes.\n\n'
        'Se houver pouco desempenho do aluno, cubra o nucleo do assunto. '
        'Se houver sinais de dificuldade, destaque esses pontos sem deixar de cobrir a base.\n\n'
        'Nao use placeholders, colchetes ou textos genericos.\n'
        'Nao crie detalhes irrelevantes ou excessivamente especificos.\n'
        'Use termos reais das amostras, da disciplina e do desempenho do aluno.\n\n'
        f'Disciplina: {discipline}\n'
        f'Disciplina: {subcategory}\n'
        f'Desempenho recente do aluno: {stats}\n'
        f'Padroes de erro mais frequentes: {stats.get("error_patterns")}\n'
        f'Amostras de questoes (enunciados): {samples}\n'
        'Retorne apenas o JSON no formato exigido.'
    )
    payload = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {
            'responseMimeType': 'application/json',
            'responseJsonSchema': build_schema(),
            'temperature': 0.2,
        },
    }

    endpoint = (
        'https://generativelanguage.googleapis.com/v1beta/models/'
        f'{settings.gemini_model}:generateContent'
    )
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'x-goog-api-key': settings.gemini_api_key,
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode('utf-8')
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode('utf-8')
        except Exception:
            body = ''
        raise HTTPException(
            status_code=502,
            detail=f'Gemini error: {exc.code} {body}'.strip(),
        ) from exc
    except urllib.error.URLError as exc:
        raise HTTPException(status_code=502, detail=f'Gemini unavailable: {exc}') from exc

    data = json.loads(raw)
    candidates = data.get('candidates') or []
    for candidate in candidates:
        content = candidate.get('content') or {}
        parts = content.get('parts') or []
        for part in parts:
            text = part.get('text')
            if text:
                return normalize_summary_payload(json.loads(text))

    raise HTTPException(status_code=500, detail='Invalid Gemini response')
