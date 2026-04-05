from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import get_attempt_history_table, get_questions_table
from app.db.session import engine
from app.services.profile_score.constants import (
    SUBCATEGORY_ATTENTION_ACCURACY_THRESHOLD,
)
from app.services.profile_score.repository import fetch_profile_metrics
from app.services.study_plan.repository import (
    fetch_study_plan_row,
    parse_priority_disciplines,
)
from app.services.summaries import fetch_question_total

MAX_RECOMMENDATIONS = 4


def fetch_home_recommendations(db: Session, *, user_id: int) -> dict[str, object]:
    metrics = fetch_profile_metrics(db, user_id)
    study_plan_row = fetch_study_plan_row(db, user_id)
    priority_disciplines = parse_priority_disciplines(
        None if study_plan_row is None else study_plan_row.get('priority_disciplines_json')
    )

    items: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()

    weakest = metrics.get('weakest_subcategory')
    if isinstance(weakest, dict):
        weakest_item = _build_weakest_recommendation(db, weakest)
        if weakest_item is not None:
            items.append(weakest_item)
            seen.add(_recommendation_key(weakest_item))

    for discipline in priority_disciplines:
        candidate = _select_best_candidate(
            _fetch_subcategory_candidates(
                db,
                user_id=user_id,
                discipline=discipline,
            ),
            seen=seen,
        )
        if candidate is None:
            continue

        item = _build_candidate_recommendation(
            candidate,
            source='priority_discipline',
        )
        items.append(item)
        seen.add(_recommendation_key(item))
        if len(items) >= MAX_RECOMMENDATIONS:
            break

    if len(items) < MAX_RECOMMENDATIONS:
        for candidate in _fetch_subcategory_candidates(db, user_id=user_id):
            key = _candidate_key(candidate)
            if key in seen:
                continue
            item = _build_candidate_recommendation(
                candidate,
                source='coverage_gap',
            )
            items.append(item)
            seen.add(key)
            if len(items) >= MAX_RECOMMENDATIONS:
                break

    return {
        'title': 'Recomendado para Hoje',
        'subtitle': _build_section_subtitle(
            items=items,
            has_priority_disciplines=bool(priority_disciplines),
        ),
        'items': items,
    }


def _build_weakest_recommendation(
    db: Session,
    weakest: dict[str, object],
) -> dict[str, object] | None:
    discipline = str(weakest.get('discipline') or '').strip()
    subcategory = str(weakest.get('subcategory') or '').strip()
    total_attempts = int(weakest.get('total_attempts') or 0)

    if not discipline or not subcategory or total_attempts <= 0:
        return None

    accuracy_percent = round(float(weakest.get('accuracy_percent') or 0.0), 1)
    total_questions = fetch_question_total(db, discipline, subcategory)
    badge_tone = _tone_for_accuracy(accuracy_percent)

    return {
        'title': subcategory,
        'discipline': discipline,
        'subcategory': subcategory,
        'description': (
            'Subcategoria com menor precisao recente e espaco claro para reforco.'
        ),
        'badge_label': _badge_label(badge_tone),
        'badge_tone': badge_tone,
        'count_label': _count_label(total_questions, total_attempts),
        'reason_label': 'Menor precisao recente',
        'source': 'weakest_subcategory',
        'accuracy_percent': accuracy_percent,
        'total_attempts': total_attempts,
        'total_questions': total_questions,
    }


def _fetch_subcategory_candidates(
    db: Session,
    *,
    user_id: int,
    discipline: str | None = None,
) -> list[dict[str, object]]:
    questions = get_questions_table(engine, settings.question_table)
    attempt_history = get_attempt_history_table(settings.attempt_history_table)

    if 'disciplina' not in questions.c or 'subcategoria' not in questions.c:
        return []

    question_stmt = (
        select(
            questions.c.disciplina.label('discipline'),
            questions.c.subcategoria.label('subcategory'),
            func.count().label('total_questions'),
        )
        .where(questions.c.disciplina.is_not(None))
        .where(questions.c.subcategoria.is_not(None))
    )
    if discipline:
        question_stmt = question_stmt.where(questions.c.disciplina == discipline)
    question_stmt = question_stmt.group_by(
        questions.c.disciplina,
        questions.c.subcategoria,
    )

    attempt_stmt = (
        select(
            attempt_history.c.discipline.label('discipline'),
            attempt_history.c.subcategory.label('subcategory'),
            func.count().label('total_attempts'),
            func.sum(
                case((attempt_history.c.is_correct.is_(True), 1), else_=0)
            ).label('total_correct'),
        )
        .where(attempt_history.c.user_id == user_id)
        .where(attempt_history.c.discipline.is_not(None))
        .where(attempt_history.c.subcategory.is_not(None))
    )
    if discipline:
        attempt_stmt = attempt_stmt.where(attempt_history.c.discipline == discipline)
    attempt_stmt = attempt_stmt.group_by(
        attempt_history.c.discipline,
        attempt_history.c.subcategory,
    )

    question_rows = db.execute(question_stmt).all()
    attempt_rows = db.execute(attempt_stmt).all()

    attempt_lookup = {
        (
            str(row.discipline or '').strip().casefold(),
            str(row.subcategory or '').strip().casefold(),
        ): {
            'total_attempts': int(row.total_attempts or 0),
            'total_correct': int(row.total_correct or 0),
        }
        for row in attempt_rows
        if str(row.discipline or '').strip() and str(row.subcategory or '').strip()
    }

    candidates: list[dict[str, object]] = []
    for row in question_rows:
        normalized_discipline = str(row.discipline or '').strip()
        normalized_subcategory = str(row.subcategory or '').strip()
        if not normalized_discipline or not normalized_subcategory:
            continue

        key = (
            normalized_discipline.casefold(),
            normalized_subcategory.casefold(),
        )
        attempts = attempt_lookup.get(key, {})
        total_attempts = int(attempts.get('total_attempts') or 0)
        total_correct = int(attempts.get('total_correct') or 0)
        accuracy_percent = (
            round((total_correct / total_attempts) * 100, 1)
            if total_attempts > 0
            else None
        )
        candidates.append(
            {
                'discipline': normalized_discipline,
                'subcategory': normalized_subcategory,
                'total_questions': int(row.total_questions or 0),
                'total_attempts': total_attempts,
                'accuracy_percent': accuracy_percent,
            }
        )

    return sorted(candidates, key=_candidate_rank)


def _candidate_rank(candidate: dict[str, object]) -> tuple[object, ...]:
    total_attempts = int(candidate.get('total_attempts') or 0)
    total_questions = int(candidate.get('total_questions') or 0)
    accuracy_percent = candidate.get('accuracy_percent')
    coverage_ratio = (
        total_attempts / total_questions
        if total_attempts > 0 and total_questions > 0
        else 0.0
    )

    if total_attempts <= 0:
        return (0, -total_questions, str(candidate.get('subcategory') or '').casefold())

    return (
        1,
        float(accuracy_percent if accuracy_percent is not None else 100.0),
        coverage_ratio,
        -total_questions,
        str(candidate.get('subcategory') or '').casefold(),
    )


def _select_best_candidate(
    candidates: list[dict[str, object]],
    *,
    seen: set[tuple[str, str]],
) -> dict[str, object] | None:
    for candidate in candidates:
        if _candidate_key(candidate) in seen:
            continue
        return candidate
    return None


def _build_candidate_recommendation(
    candidate: dict[str, object],
    *,
    source: str,
) -> dict[str, object]:
    discipline = str(candidate.get('discipline') or '').strip()
    subcategory = str(candidate.get('subcategory') or '').strip()
    total_questions = int(candidate.get('total_questions') or 0)
    total_attempts = int(candidate.get('total_attempts') or 0)
    accuracy_percent = candidate.get('accuracy_percent')
    tone = _tone_for_candidate(
        source=source,
        total_attempts=total_attempts,
        accuracy_percent=accuracy_percent,
    )

    return {
        'title': subcategory,
        'discipline': discipline,
        'subcategory': subcategory,
        'description': _description_for_candidate(
            source=source,
            total_attempts=total_attempts,
            accuracy_percent=accuracy_percent,
        ),
        'badge_label': _badge_label(tone),
        'badge_tone': tone,
        'count_label': _count_label(total_questions, total_attempts),
        'reason_label': _reason_label_for_candidate(
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


def _description_for_candidate(
    *,
    source: str,
    total_attempts: int,
    accuracy_percent: object,
) -> str:
    if source == 'priority_discipline':
        if total_attempts <= 0:
            return 'Disciplina prioritaria do seu plano ainda sem cobertura recente.'
        if _is_attention_accuracy(accuracy_percent):
            return 'Disciplina prioritaria com desempenho abaixo do ideal nesta subcategoria.'
        return 'Boa frente para manter ritmo e consolidar repertorio hoje.'

    if total_attempts <= 0:
        return 'Boa opcao para abrir cobertura e ganhar tracao nesta frente.'
    if _is_attention_accuracy(accuracy_percent):
        return 'Subcategoria com espaco para reforco antes de avancar para a proxima etapa.'
    return 'Boa opcao para ampliar cobertura e manter consistencia hoje.'


def _reason_label_for_candidate(
    *,
    source: str,
    total_attempts: int,
    accuracy_percent: object,
) -> str:
    if source == 'priority_discipline':
        if total_attempts <= 0:
            return 'Sem cobertura recente'
        if _is_attention_accuracy(accuracy_percent):
            return 'Prioridade com baixa precisao'
        return 'Prioridade do plano'

    if total_attempts <= 0:
        return 'Ampliar cobertura'
    if _is_attention_accuracy(accuracy_percent):
        return 'Precisao abaixo do ideal'
    return 'Manter ritmo'


def _tone_for_candidate(
    *,
    source: str,
    total_attempts: int,
    accuracy_percent: object,
) -> str:
    if source == 'priority_discipline' and total_attempts <= 0:
        return 'moderate'
    return _tone_for_accuracy(accuracy_percent)


def _tone_for_accuracy(accuracy_percent: object) -> str:
    if _is_attention_accuracy(accuracy_percent):
        return 'critical'
    return 'moderate'


def _is_attention_accuracy(accuracy_percent: object) -> bool:
    if accuracy_percent is None:
        return False
    return float(accuracy_percent) < SUBCATEGORY_ATTENTION_ACCURACY_THRESHOLD


def _badge_label(tone: str) -> str:
    return 'Critico' if tone == 'critical' else 'Moderado'


def _count_label(total_questions: int, total_attempts: int) -> str:
    if total_questions > 0:
        label = 'questao' if total_questions == 1 else 'questoes'
        return f'{total_questions} {label}'

    if total_attempts > 0:
        label = 'tentativa' if total_attempts == 1 else 'tentativas'
        return f'{total_attempts} {label}'

    return 'Sem volume mapeado'


def _build_section_subtitle(
    *,
    items: list[dict[str, object]],
    has_priority_disciplines: bool,
) -> str:
    has_weakest = any(item.get('source') == 'weakest_subcategory' for item in items)
    has_priority = any(item.get('source') == 'priority_discipline' for item in items)

    if has_weakest and has_priority:
        return 'Priorizando pontos de atencao e frentes do seu plano'
    if has_weakest:
        return 'Priorizando subcategorias que pedem mais atencao agora'
    if has_priority or has_priority_disciplines:
        return 'Priorizando disciplinas marcadas no seu plano'
    return 'Priorizando subcategorias para ampliar cobertura hoje'


def _candidate_key(candidate: dict[str, object]) -> tuple[str, str]:
    return (
        str(candidate.get('discipline') or '').strip().casefold(),
        str(candidate.get('subcategory') or '').strip().casefold(),
    )


def _recommendation_key(item: dict[str, object]) -> tuple[str, str]:
    return (
        str(item.get('discipline') or '').strip().casefold(),
        str(item.get('subcategory') or '').strip().casefold(),
    )
