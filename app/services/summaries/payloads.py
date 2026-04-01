import json

from fastapi import HTTPException

MAX_SUMMARY_NODES = 4
MAX_ITEMS_PER_NODE = 3


def locked_summary(discipline: str, subcategory: str) -> dict:
    return {
        'title': f'{subcategory} - Mapa mental',
        'discipline': discipline,
        'subcategory': subcategory,
        'nodes': [],
        'locked_until_complete': True,
        'locked_message': 'Conclua o simulado para liberar seu mapa mental personalizado.',
    }


def stats_payload(stats: dict | None) -> dict:
    if not stats:
        return {
            'total_attempts': 0,
            'total_correct': 0,
            'accuracy_percent': 0.0,
            'last_attempt_at': None,
        }
    return {
        'total_attempts': stats.get('total_attempts', 0),
        'total_correct': stats.get('total_correct', 0),
        'accuracy_percent': stats.get('accuracy_percent', 0.0),
        'last_attempt_at': stats.get('latest_attempt_at'),
    }


def attach_stats(payload: dict, stats: dict | None) -> dict:
    response = dict(payload)
    response['stats'] = stats_payload(stats)
    return response


def normalize_required_summary_fields(
    payload: dict,
) -> tuple[str, str, list, str | None]:
    discipline = payload.get('discipline')
    subcategory = payload.get('subcategory')
    nodes = payload.get('nodes')
    title = payload.get('title')

    if not discipline or not str(discipline).strip():
        raise HTTPException(status_code=400, detail='discipline is required')
    if not subcategory or not str(subcategory).strip():
        raise HTTPException(status_code=400, detail='subcategory is required')
    if not isinstance(nodes, list) or not nodes:
        raise HTTPException(status_code=400, detail='nodes is required')

    return str(discipline).strip(), str(subcategory).strip(), nodes, title


def load_summary_payload(payload_json: str) -> dict:
    try:
        return normalize_summary_payload(json.loads(payload_json))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail='Invalid summary JSON') from exc


def default_summary(discipline: str, subcategory: str) -> dict:
    return normalize_summary_payload(
        {
            'title': f'{subcategory} - Resumo',
            'discipline': discipline,
            'subcategory': subcategory,
            'nodes': [
                {
                    'title': 'Conceitos-chave',
                    'items': [
                        'Definicoes essenciais',
                        'Grandezas e unidades',
                        'Relacoes fundamentais',
                    ],
                },
                {
                    'title': 'Formulas e Leis',
                    'items': [
                        'Formulas principais',
                        'Condicoes de uso',
                        'Observacoes rapidas',
                    ],
                },
                {
                    'title': 'Interpretacao',
                    'items': [
                        'Leitura de graficos',
                        'Palavras-chave do enunciado',
                        'Unidades no contexto',
                    ],
                },
                {
                    'title': 'Estrategias',
                    'items': [
                        'Passo a passo tipico',
                        'Checagem de sinais',
                        'Revisao de alternativas',
                    ],
                },
                {
                    'title': 'Erros comuns',
                    'items': [
                        'Troca de unidades',
                        'Aplicacao fora do dominio',
                        'Interpretacao incorreta',
                    ],
                },
            ],
        }
    )


def trim_text(value: str, limit: int) -> str:
    text = ' '.join(value.split()).strip()
    if len(text) <= limit:
        return text
    return f'{text[: limit - 3].rstrip()}...'


def clean_text(value: str) -> str:
    return ' '.join(value.split()).strip()


def normalize_summary_payload(payload: dict) -> dict:
    raw_nodes = payload.get('nodes')
    normalized_nodes = []

    if isinstance(raw_nodes, list):
        for raw_node in raw_nodes[:MAX_SUMMARY_NODES]:
            if not isinstance(raw_node, dict):
                continue

            title = trim_text(str(raw_node.get('title') or ''), 48)
            raw_items = raw_node.get('items')
            if not title or not isinstance(raw_items, list):
                continue

            items = []
            for raw_item in raw_items[:MAX_ITEMS_PER_NODE]:
                item = clean_text(str(raw_item or ''))
                if item:
                    items.append(item)

            if items:
                normalized_nodes.append({'title': title, 'items': items})

    return {
        'title': trim_text(
            str(payload.get('title') or payload.get('subcategory') or 'Resumo'),
            80,
        ),
        'discipline': str(payload.get('discipline') or ''),
        'subcategory': str(payload.get('subcategory') or ''),
        'nodes': normalized_nodes,
    }
