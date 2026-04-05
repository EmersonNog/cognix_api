from app.services.profile_score.constants import (
    SUBCATEGORY_ATTENTION_ACCURACY_THRESHOLD,
)


def build_weakest_recommendation(
    weakest: dict[str, object],
    *,
    total_questions: int,
) -> dict[str, object] | None:
    discipline = str(weakest.get('discipline') or '').strip()
    subcategory = str(weakest.get('subcategory') or '').strip()
    total_attempts = int(weakest.get('total_attempts') or 0)

    if not discipline or not subcategory or total_attempts <= 0:
        return None

    accuracy_percent = round(float(weakest.get('accuracy_percent') or 0.0), 1)
    badge_tone = tone_for_accuracy(accuracy_percent)

    return {
        'title': subcategory,
        'discipline': discipline,
        'subcategory': subcategory,
        'description': (
            'Disciplina com menor precisão recente e espaco claro para reforço.'
        ),
        'badge_label': badge_label(badge_tone),
        'badge_tone': badge_tone,
        'count_label': count_label(total_questions, total_attempts),
        'reason_label': 'Menor precisao recente',
        'source': 'weakest_subcategory',
        'accuracy_percent': accuracy_percent,
        'total_attempts': total_attempts,
        'total_questions': total_questions,
    }


def build_candidate_recommendation(
    candidate: dict[str, object],
    *,
    source: str,
) -> dict[str, object]:
    discipline = str(candidate.get('discipline') or '').strip()
    subcategory = str(candidate.get('subcategory') or '').strip()
    total_questions = int(candidate.get('total_questions') or 0)
    total_attempts = int(candidate.get('total_attempts') or 0)
    accuracy_percent = candidate.get('accuracy_percent')
    tone = tone_for_candidate(
        source=source,
        total_attempts=total_attempts,
        accuracy_percent=accuracy_percent,
    )

    return {
        'title': subcategory,
        'discipline': discipline,
        'subcategory': subcategory,
        'description': description_for_candidate(
            source=source,
            total_attempts=total_attempts,
            accuracy_percent=accuracy_percent,
        ),
        'badge_label': badge_label(tone),
        'badge_tone': tone,
        'count_label': count_label(total_questions, total_attempts),
        'reason_label': reason_label_for_candidate(
            source=source,
            total_attempts=total_attempts,
            accuracy_percent=accuracy_percent,
        ),
        'source': source,
        'accuracy_percent': round(float(accuracy_percent or 0.0), 1)
        if accuracy_percent is not None
        else None,
        'total_attempts': total_attempts,
        'total_questions': total_questions,
    }


def description_for_candidate(
    *,
    source: str,
    total_attempts: int,
    accuracy_percent: object,
) -> str:
    if source == 'priority_discipline':
        if total_attempts <= 0:
            return 'Disciplina prioritária do seu plano ainda sem cobertura recente.'
        if is_attention_accuracy(accuracy_percent):
            return 'Disciplina prioritária com desempenho abaixo do ideal nesta disciplina.'
        return 'Boa frente para manter ritmo e consolidar repertório hoje.'

    if total_attempts <= 0:
        return 'Boa opção para abrir cobertura e ganhar tração nesta frente.'
    if is_attention_accuracy(accuracy_percent):
        return 'Disciplina com espaço para reforço antes de avançar para a próxima etapa.'
    return 'Boa opção para ampliar cobertura e manter consistência hoje.'


def reason_label_for_candidate(
    *,
    source: str,
    total_attempts: int,
    accuracy_percent: object,
) -> str:
    if source == 'priority_discipline':
        if total_attempts <= 0:
            return 'Sem cobertura recente'
        if is_attention_accuracy(accuracy_percent):
            return 'Prioridade com baixa precisão'
        return 'Prioridade do plano'

    if total_attempts <= 0:
        return 'Ampliar cobertura'
    if is_attention_accuracy(accuracy_percent):
        return 'Precisão abaixo do ideal'
    return 'Manter ritmo'


def tone_for_candidate(
    *,
    source: str,
    total_attempts: int,
    accuracy_percent: object,
) -> str:
    if source == 'priority_discipline' and total_attempts <= 0:
        return 'moderate'
    return tone_for_accuracy(accuracy_percent)


def tone_for_accuracy(accuracy_percent: object) -> str:
    if is_attention_accuracy(accuracy_percent):
        return 'critical'
    return 'moderate'


def is_attention_accuracy(accuracy_percent: object) -> bool:
    if accuracy_percent is None:
        return False
    return float(accuracy_percent) < SUBCATEGORY_ATTENTION_ACCURACY_THRESHOLD


def badge_label(tone: str) -> str:
    return 'Critico' if tone == 'critical' else 'Moderado'


def count_label(total_questions: int, total_attempts: int) -> str:
    if total_questions > 0:
        label = 'questao' if total_questions == 1 else 'questoes'
        return f'{total_questions} {label}'

    if total_attempts > 0:
        label = 'tentativa' if total_attempts == 1 else 'tentativas'
        return f'{total_attempts} {label}'

    return 'Sem volume mapeado'


def build_section_subtitle(
    *,
    items: list[dict[str, object]],
    has_priority_disciplines: bool,
) -> str:
    has_weakest = any(item.get('source') == 'weakest_subcategory' for item in items)
    has_priority = any(item.get('source') == 'priority_discipline' for item in items)

    if has_weakest and has_priority:
        return 'Priorizando pontos de atenção e frentes do seu plano'
    if has_weakest:
        return 'Priorizando disciplinas que pedem mais atenção agora'
    if has_priority or has_priority_disciplines:
        return 'Priorizando disciplinas marcadas no seu plano'
    return 'Priorizando disciplinas para ampliar cobertura hoje'
