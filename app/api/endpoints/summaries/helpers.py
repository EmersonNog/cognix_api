from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import get_summaries_table
from app.services.summaries import (
    default_summary,
    insert_base_summary_if_missing,
    load_summary_payload,
    upsert_base_summary,
)


def has_summary_nodes(payload: dict) -> bool:
    nodes = payload.get('nodes')
    return isinstance(nodes, list) and bool(nodes)


def build_default_payload(discipline: str, subcategory: str) -> dict:
    return default_summary(discipline, subcategory)


def resolve_base_summary_payload(
    db: Session,
    discipline: str,
    subcategory: str,
    payload: dict,
) -> dict:
    if has_summary_nodes(payload):
        return payload

    fallback = build_default_payload(discipline, subcategory)
    upsert_base_summary(db, discipline, subcategory, fallback)
    return fallback


def load_base_summary(db: Session, discipline: str, subcategory: str) -> dict:
    summaries = get_summaries_table(settings.summaries_table)
    row = db.execute(
        select(summaries)
        .where(summaries.c.discipline == discipline)
        .where(summaries.c.subcategory == subcategory)
    ).mappings().first()

    if row is None:
        payload = build_default_payload(discipline, subcategory)
        insert_base_summary_if_missing(db, discipline, subcategory, payload)
        return payload

    payload = load_summary_payload(row['payload_json'])
    return resolve_base_summary_payload(db, discipline, subcategory, payload)
