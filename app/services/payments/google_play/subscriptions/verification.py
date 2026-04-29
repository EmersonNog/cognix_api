from __future__ import annotations

from dataclasses import replace

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.payments.abacatepay.subscriptions.identity import hash_email

from .client import (
    acknowledge_google_play_subscription_purchase,
    fetch_google_play_subscription_purchase,
)
from .records import upsert_google_play_subscription
from .status import (
    GooglePlaySubscriptionSnapshot,
    google_play_product_ids,
    snapshot_from_google_play_payload,
)


def verify_google_play_subscription_purchase(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str,
    email: str | None,
    package_name: str,
    product_id: str,
    purchase_token: str,
) -> None:
    _validate_request(
        package_name=package_name,
        product_id=product_id,
        purchase_token=purchase_token,
    )

    google_payload = fetch_google_play_subscription_purchase(
        package_name=package_name,
        purchase_token=purchase_token,
    )
    snapshot = snapshot_from_google_play_payload(
        google_payload,
        expected_product_id=product_id,
    )
    if _should_acknowledge_purchase(snapshot):
        acknowledge_google_play_subscription_purchase(
            package_name=package_name,
            product_id=product_id,
            purchase_token=purchase_token,
        )
        snapshot = replace(
            snapshot,
            acknowledgement_state='ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED',
        )

    upsert_google_play_subscription(
        db,
        user_id=user_id,
        firebase_uid=firebase_uid,
        email_hash=hash_email(email),
        package_name=package_name,
        purchase_token=purchase_token,
        snapshot=snapshot,
        raw_payload=google_payload,
    )
    db.commit()


def _validate_request(
    *,
    package_name: str,
    product_id: str,
    purchase_token: str,
) -> None:
    if package_name != settings.google_play_package_name:
        raise HTTPException(
            status_code=400,
            detail='Pacote do app inválido para esta assinatura.',
        )

    if product_id not in google_play_product_ids():
        raise HTTPException(
            status_code=400,
            detail='Plano Google Play inválido.',
        )

    if not purchase_token.strip():
        raise HTTPException(
            status_code=400,
            detail='Token de compra ausente.',
        )


def _should_acknowledge_purchase(snapshot: GooglePlaySubscriptionSnapshot) -> bool:
    return (
        snapshot.has_access
        and snapshot.acknowledgement_state != 'ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED'
    )
