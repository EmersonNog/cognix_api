from __future__ import annotations

from sqlalchemy.orm import Session

from ..persistence.records import link_subscription_to_user


def link_subscription_if_needed(
    db: Session,
    *,
    subscription: dict,
    user_id: int,
    firebase_uid: str | None,
) -> None:
    if subscription.get('user_id') == user_id and (
        not firebase_uid or subscription.get('firebase_uid') == firebase_uid
    ):
        return

    link_subscription_to_user(
        db,
        subscription_id=int(subscription['id']),
        user_id=user_id,
        firebase_uid=firebase_uid,
    )
