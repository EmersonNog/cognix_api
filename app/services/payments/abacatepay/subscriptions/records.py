from __future__ import annotations

from sqlalchemy import and_, desc, insert, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.datetime_utils import utc_now
from app.db.models import get_payment_subscriptions_table


ACTIVE_STATUSES = {'active', 'checkout_created'}
CANCELABLE_STATUSES = {'active'}


def record_subscription_checkout_created(
    db: Session,
    *,
    plan_id: str,
    product_id: str,
    tax_id_hash: str,
    email_hash: str,
    external_customer_id: str,
    external_id: str,
    checkout_id: str | None,
    checkout_url: str | None,
) -> None:
    table = get_payment_subscriptions_table(settings.payment_subscriptions_table)
    now = utc_now()

    db.execute(
        insert(table).values(
            plan_id=plan_id,
            product_id=product_id,
            tax_id_hash=tax_id_hash,
            email_hash=email_hash,
            external_customer_id=external_customer_id,
            external_id=external_id,
            checkout_id=checkout_id,
            checkout_url=checkout_url,
            status='checkout_created',
            created_at=now,
            updated_at=now,
        )
    )


def mark_subscription_active(
    db: Session,
    *,
    external_id: str,
    external_subscription_id: str | None,
    checkout_id: str | None,
    checkout_url: str | None,
) -> None:
    table = get_payment_subscriptions_table(settings.payment_subscriptions_table)
    values = {
        'status': 'active',
        'updated_at': utc_now(),
    }

    if external_subscription_id:
        values['external_subscription_id'] = external_subscription_id
    if checkout_id:
        values['checkout_id'] = checkout_id
    if checkout_url:
        values['checkout_url'] = checkout_url

    db.execute(update(table).where(table.c.external_id == external_id).values(**values))


def mark_subscription_cancelled(
    db: Session,
    *,
    subscription_id: int,
) -> None:
    table = get_payment_subscriptions_table(settings.payment_subscriptions_table)
    now = utc_now()
    db.execute(
        update(table)
        .where(table.c.id == subscription_id)
        .values(
            status='cancelled',
            cancel_requested_at=now,
            cancelled_at=now,
            updated_at=now,
        )
    )


def mark_subscription_cancelled_by_external_id(
    db: Session,
    *,
    external_id: str,
    external_subscription_id: str | None,
) -> None:
    table = get_payment_subscriptions_table(settings.payment_subscriptions_table)
    now = utc_now()
    values = {
        'status': 'cancelled',
        'cancelled_at': now,
        'updated_at': now,
    }

    if external_subscription_id:
        values['external_subscription_id'] = external_subscription_id

    db.execute(update(table).where(table.c.external_id == external_id).values(**values))


def find_current_subscription_for_user(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str | None,
    email_hash: str | None,
) -> dict | None:
    table = get_payment_subscriptions_table(settings.payment_subscriptions_table)
    filters = [table.c.user_id == user_id]

    if firebase_uid:
        filters.append(table.c.firebase_uid == firebase_uid)
    if email_hash:
        filters.append(table.c.email_hash == email_hash)

    row = db.execute(
        select(table)
        .where(
            or_(*filters),
            table.c.status.in_(ACTIVE_STATUSES | {'cancelled'}),
        )
        .order_by(
            desc(table.c.status == 'active'),
            desc(table.c.updated_at),
            desc(table.c.id),
        )
        .limit(1)
    ).mappings().first()

    return dict(row) if row else None


def find_cancelable_subscription_for_user(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str | None,
    email_hash: str | None,
) -> dict | None:
    table = get_payment_subscriptions_table(settings.payment_subscriptions_table)
    filters = [table.c.user_id == user_id]

    if firebase_uid:
        filters.append(table.c.firebase_uid == firebase_uid)
    if email_hash:
        filters.append(table.c.email_hash == email_hash)

    row = db.execute(
        select(table)
        .where(
            or_(*filters),
            table.c.status.in_(CANCELABLE_STATUSES),
        )
        .order_by(desc(table.c.updated_at), desc(table.c.id))
        .limit(1)
    ).mappings().first()

    return dict(row) if row else None


def link_subscription_to_user(
    db: Session,
    *,
    subscription_id: int,
    user_id: int,
    firebase_uid: str | None,
) -> None:
    table = get_payment_subscriptions_table(settings.payment_subscriptions_table)
    values = {
        'user_id': user_id,
        'updated_at': utc_now(),
    }

    if firebase_uid:
        values['firebase_uid'] = firebase_uid

    db.execute(update(table).where(table.c.id == subscription_id).values(**values))
