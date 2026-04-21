import hashlib
import json


def build_insight_fingerprint(metrics: dict, score_data: dict) -> str:
    strongest = metrics.get('strongest_subcategory') or {}
    weakest = metrics.get('weakest_subcategory') or {}
    question_rows = metrics.get('question_rows') or []

    payload = {
        'insight_schema_version': 2,
        'score': score_data.get('score'),
        'level': score_data.get('level'),
        'recent_index': score_data.get('recent_index'),
        'questions_answered_bucket': int((metrics.get('total_questions') or 0) / 10),
        'accuracy_percent_bucket': round(float(metrics.get('accuracy_percent') or 0.0), 0),
        'completed_sessions': metrics.get('completed_sessions'),
        'active_days_last_30': metrics.get('active_days_last_30'),
        'current_streak_days': metrics.get('current_streak_days'),
        'attention_subcategories_count': metrics.get('attention_subcategories_count'),
        'top_disciplines': [
            {
                'discipline': row[0],
                'count_bucket': int((int(row[1] or 0)) / 5),
            }
            for row in question_rows[:4]
            if row and row[0]
        ],
        'strongest_subcategory': {
            'discipline': strongest.get('discipline'),
            'subcategory': strongest.get('subcategory'),
            'accuracy_percent_bucket': round(
                float(strongest.get('accuracy_percent') or 0.0),
                0,
            ),
        },
        'weakest_subcategory': {
            'discipline': weakest.get('discipline'),
            'subcategory': weakest.get('subcategory'),
            'accuracy_percent_bucket': round(
                float(weakest.get('accuracy_percent') or 0.0),
                0,
            ),
        },
    }

    raw = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def build_insight_prompt(metrics: dict, score_data: dict) -> str:
    strongest = metrics.get('strongest_subcategory') or {}
    weakest = metrics.get('weakest_subcategory') or {}
    question_rows = metrics.get('question_rows') or []
    top_disciplines = [
        {'discipline': row[0], 'count': int(row[1] or 0)}
        for row in question_rows[:4]
        if row and row[0]
    ]

    total_questions = int(metrics.get('total_questions') or 0)
    active_days_last_30 = int(metrics.get('active_days_last_30') or 0)
    completed_sessions = int(metrics.get('completed_sessions') or 0)
    leader_share_percent = 0
    if total_questions > 0 and top_disciplines:
        leader_share_percent = round((top_disciplines[0]['count'] / total_questions) * 100)

    insight_payload = {
        'score': score_data.get('score'),
        'level': score_data.get('level'),
        'recent_index': score_data.get('recent_index'),
        'questions_answered': total_questions,
        'total_correct': metrics.get('total_correct'),
        'accuracy_percent': metrics.get('accuracy_percent'),
        'completed_sessions': completed_sessions,
        'total_study_seconds': metrics.get('total_study_seconds'),
        'active_days_last_30': active_days_last_30,
        'current_streak_days': metrics.get('current_streak_days'),
        'disciplines': top_disciplines,
        'leader_discipline': top_disciplines[0]['discipline'] if top_disciplines else None,
        'leader_share_percent': leader_share_percent,
        'strongest_subcategory': strongest,
        'weakest_subcategory': weakest,
        'attention_subcategories_count': metrics.get('attention_subcategories_count'),
        'sample_quality': _sample_quality_label(
            total_questions=total_questions,
            completed_sessions=completed_sessions,
            active_days_last_30=active_days_last_30,
        ),
    }

    return (
        'Você é um analista pedagógico do Cognix. '
        'Receba métricas reais de estudo e responda em JSON com as chaves: '
        '`title`, `summary`, `priority`, `risk_level`, `next_action`, `confidence`. '
        'Regras: '
        '1) Não invente números. '
        '2) Use tom claro, humano e direto. '
        '3) O title deve ter no máximo 4 palavras. '
        '4) O summary deve ter entre 2 e 4 frases curtas, explicando panorama atual, '
        'qualidade do desempenho e próximo melhor movimento. '
        '5) priority deve ser curta e prática, como "Revisar Álgebra". '
        '6) risk_level deve ser exatamente "baixo", "medio" ou "alto". '
        '7) next_action deve ser uma ação objetiva, em uma frase curta. '
        '8) confidence deve ser um número decimal entre 0.0 e 1.0. '
        '9) Se houver pouca base, diga isso com honestidade. '
        '10) Diferencie claramente presença/volume de prioridade de revisão. '
        'Presença indica onde há mais questões respondidas. Prioridade indica onde agir agora. '
        '11) Não diga "o foco atual e X" se X for apenas a prioridade de revisão. '
        'Se o volume estiver em uma disciplina e a prioridade estiver em outra, deixe isso explicito. '
        '12) Se sample_quality for "baixa", trate as conclusões como leitura inicial e evite afirmacões fortes. '
        '13) Responda apenas JSON valido.\n\n'
        f'DADOS:\n{json.dumps(insight_payload, ensure_ascii=False)}'
    )


def _sample_quality_label(
    *,
    total_questions: int,
    completed_sessions: int,
    active_days_last_30: int,
) -> str:
    if total_questions < 12 or active_days_last_30 < 3:
        return 'baixa'
    if total_questions < 30 or completed_sessions < 3:
        return 'media'
    return 'alta'
