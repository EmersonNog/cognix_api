from __future__ import annotations

import json

from fastapi import HTTPException
from sqlalchemy import desc, insert, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.datetime_utils import utc_now
from app.db.models import get_google_play_subscriptions_table

from .status import GooglePlaySubscriptionSnapshot


ACTIVE_STATUSES = {'active', 'cancelled'}
CURRENT_STATUS_CANDIDATES = ACTIVE_STATUSES | {'expired', 'pending'}
MONTHLY_INTRO_OFFER_IDS = {'app-first-month-990'}


def upsert_google_play_subscription(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str,
    email_hash: str | None,
    package_name: str,
    purchase_token: str,
    snapshot: GooglePlaySubscriptionSnapshot,
    raw_payload: dict,
) -> None:
    table = get_google_play_subscriptions_table(
        settings.google_play_subscriptions_table
    )
    existing = _find_subscription_by_token(db, purchase_token=purchase_token)
    if existing is not None and existing.get('user_id') != user_id:
        raise HTTPException(
            status_code=409,
            detail={
                'code': 'subscription_linked_to_another_account',
                'message': (
                    'Esta assinatura Google Play já esta vinculada a outra '
                    'conta Cognix. Entre nessa conta para usar o Premium. '
                    'Para usar Premium nesta conta, cancele a assinatura no '
                    'Google Play e aguarde o fim do período pago antes de '
                    'assinar novamente.'
                ),
            },
        )

    now = utc_now()
    values = {
        'user_id': user_id,
        'firebase_uid': firebase_uid,
        'email_hash': email_hash,
        'package_name': package_name,
        'product_id': snapshot.product_id,
        'purchase_token': purchase_token,
        'latest_order_id': snapshot.latest_order_id,
        'base_plan_id': snapshot.base_plan_id,
        'offer_id': snapshot.offer_id,
        'status': snapshot.status,
        'subscription_state': snapshot.subscription_state,
        'acknowledgement_state': snapshot.acknowledgement_state,
        'auto_renewing': snapshot.auto_renewing,
        'current_period_ends_at': snapshot.current_period_ends_at,
        'raw_payload': json.dumps(raw_payload, ensure_ascii=True),
        'updated_at': now,
    }

    if existing is None:
        db.execute(insert(table).values(**values, created_at=now))
        return

    db.execute(
        update(table)
        .where(table.c.purchase_token == purchase_token)
        .values(**values)
    )


def find_current_google_play_subscription_for_user(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str | None,
    email_hash: str | None,
) -> dict | None:
    table = get_google_play_subscriptions_table(
        settings.google_play_subscriptions_table
    )
    identity_filters = _user_identity_filters(
        table,
        user_id=user_id,
        firebase_uid=firebase_uid,
        email_hash=email_hash,
    )

    row = db.execute(
        select(table)
        .where(
            or_(*identity_filters),
            table.c.status.in_(CURRENT_STATUS_CANDIDATES),
        )
        .order_by(
            desc(table.c.status == 'active'),
            desc(table.c.current_period_ends_at),
            desc(table.c.updated_at),
            desc(table.c.id),
        )
        .limit(1)
    ).mappings().first()

    return dict(row) if row else None


def has_used_monthly_intro_offer(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str | None,
    email_hash: str | None,
) -> bool:
    table = get_google_play_subscriptions_table(
        settings.google_play_subscriptions_table
    )
    identity_filters = _user_identity_filters(
        table,
        user_id=user_id,
        firebase_uid=firebase_uid,
        email_hash=email_hash,
    )

    row = db.execute(
        select(table.c.id)
        .where(
            or_(*identity_filters),
            table.c.product_id == settings.google_play_product_id_monthly,
            table.c.offer_id.in_(MONTHLY_INTRO_OFFER_IDS),
        )
        .limit(1)
    ).first()

    return row is not None


def _user_identity_filters(
    table,
    *,
    user_id: int,
    firebase_uid: str | None,
    email_hash: str | None,
) -> list:
    filters = [table.c.user_id == user_id]

    if firebase_uid:
        filters.append(table.c.firebase_uid == firebase_uid)
    if email_hash:
        filters.append(table.c.email_hash == email_hash)

    return filters


def _find_subscription_by_token(
    db: Session,
    *,
    purchase_token: str,
) -> dict | None:
    table = get_google_play_subscriptions_table(
        settings.google_play_subscriptions_table
    )
    row = db.execute(
        select(table).where(table.c.purchase_token == purchase_token).limit(1)
    ).mappings().first()

    return dict(row) if row else None
