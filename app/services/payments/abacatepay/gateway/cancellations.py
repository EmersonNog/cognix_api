from __future__ import annotations

from .http import post_abacatepay

def cancel_subscription(subscription_id: str) -> None:
    post_abacatepay('/subscriptions/cancel', {'id': subscription_id})
