from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.datetime_utils import utc_now
from app.services.payments.abacatepay.subscriptions.current import (
    get_current_subscription_status as get_abacatepay_subscription_status,
)
from app.services.payments.abacatepay.subscriptions.identity import hash_email
from app.services.payments.google_play.subscriptions.current import (
    get_current_google_play_subscription_status,
)
from app.services.payments.google_play.subscriptions.records import (
    has_used_monthly_intro_offer,
)

from ..access.policies import full_access_features
from ..grants.records import find_user_grant, mark_user_grant_expired
from .subscriptions import (
    get_current_subscription_status as _get_current_subscription_status,
    monthly_intro_offer_eligible as _monthly_intro_offer_eligible_for_user,
)
from .trial_status import get_current_trial_status


def get_current_access_status(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str | None,
    email: str | None,
) -> dict[str, object]:
    subscription = get_current_subscription_status(
        db,
        user_id=user_id,
        firebase_uid=firebase_uid,
        email=email,
    )
    trial = _current_trial_status(
        db,
        user_id=user_id,
        firebase_uid=firebase_uid,
    )
    monthly_intro_offer_eligible = _monthly_intro_offer_eligible(
        db,
        user_id=user_id,
        firebase_uid=firebase_uid,
        email=email,
    )

    if subscription.get('hasAccess') is True:
        return _response(
            access_status='subscription',
            has_full_access=True,
            active_source=subscription.get('provider') or 'subscription',
            subscription=subscription,
            trial=trial,
            monthly_intro_offer_eligible=monthly_intro_offer_eligible,
        )

    if trial['isActive']:
        return _response(
            access_status='trial',
            has_full_access=True,
            active_source='trial',
            subscription=subscription,
            trial=trial,
            monthly_intro_offer_eligible=monthly_intro_offer_eligible,
        )

    access_status = 'trial_available' if trial['isAvailable'] else 'trial_expired'
    return _response(
        access_status=access_status,
        has_full_access=False,
        active_source=None,
        subscription=subscription,
        trial=trial,
        monthly_intro_offer_eligible=monthly_intro_offer_eligible,
    )


def get_current_subscription_status(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str | None,
    email: str | None,
) -> dict:
    return _get_current_subscription_status(
        db,
        user_id=user_id,
        firebase_uid=firebase_uid,
        email=email,
        google_subscription_status_getter=get_current_google_play_subscription_status,
        abacatepay_subscription_status_getter=get_abacatepay_subscription_status,
        now=utc_now,
    )


def _current_trial_status(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str | None,
) -> dict[str, object]:
    return get_current_trial_status(
        db,
        user_id=user_id,
        firebase_uid=firebase_uid,
        find_grant=find_user_grant,
        mark_expired=mark_user_grant_expired,
        now=utc_now,
    )


def _response(
    *,
    access_status: str,
    has_full_access: bool,
    active_source: str | None,
    subscription: dict,
    trial: dict[str, object],
    monthly_intro_offer_eligible: bool,
) -> dict[str, object]:
    return {
        'accessStatus': access_status,
        'hasFullAccess': has_full_access,
        'activeSource': active_source,
        'eligibleForMonthlyIntroOffer': monthly_intro_offer_eligible,
        'features': full_access_features() if has_full_access else [],
        'trialAvailable': bool(trial['isAvailable']) and not has_full_access,
        'trialStatus': trial['status'],
        'trialStartedAt': trial['startedAt'],
        'trialEndsAt': trial['endsAt'],
        'subscriptionStatus': subscription.get('status'),
        'subscriptionPlanId': subscription.get('planId'),
        'subscriptionHasAccess': subscription.get('hasAccess') is True,
        'subscriptionAccessEndsAt': subscription.get('accessEndsAt'),
        'subscriptionWillCancelAtPeriodEnd': subscription.get(
            'willCancelAtPeriodEnd'
        )
        is True,
        'subscriptionCanCancel': subscription.get('canCancel') is True,
        'subscriptionProvider': subscription.get('provider'),
    }


def _monthly_intro_offer_eligible(
    db: Session,
    *,
    user_id: int,
    firebase_uid: str | None,
    email: str | None,
) -> bool:
    return _monthly_intro_offer_eligible_for_user(
        db,
        user_id=user_id,
        firebase_uid=firebase_uid,
        email=email,
        hash_user_email=hash_email,
        has_used_intro_offer=has_used_monthly_intro_offer,
    )
