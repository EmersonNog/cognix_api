import base64
import hashlib
import hmac
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.api.endpoints.payments import _validate_webhook_signature
from app.core.config import settings
from app.services.payments.abacatepay.checkout.attribution import (
    attribution_from_json,
    attribution_metadata,
    attribution_to_json,
    normalize_attribution,
)
from app.services.payments.utmify import build_utmify_paid_order_payload


class CheckoutAttributionTests(unittest.TestCase):
    def test_normalize_attribution_allows_only_known_string_values(self) -> None:
        attribution = normalize_attribution(
            {
                'utm_source': ' meta ',
                'utm_campaign': 'black\x00friday',
                'utm_content': 'x' * 350,
                'unknown': 'ignore',
                'fbclid': 123,
            }
        )

        self.assertEqual(
            attribution,
            {
                'utm_campaign': 'blackfriday',
                'utm_content': 'x' * 300,
                'utm_source': 'meta',
            },
        )

    def test_attribution_json_round_trip_revalidates_payload(self) -> None:
        raw = '{"utm_source":"google","unknown":"ignore","gclid":"abc"}'

        self.assertEqual(
            attribution_from_json(raw),
            {'gclid': 'abc', 'utm_source': 'google'},
        )
        self.assertEqual(
            attribution_to_json({'utm_source': 'google'}),
            json.dumps({'utm_source': 'google'}, separators=(',', ':'), sort_keys=True),
        )

    def test_attribution_json_and_metadata_revalidate_payloads(self) -> None:
        attribution = {
            'utm_source': ' meta ',
            'landingPage': 'https://app.example/\x7fcheckout',
            'unknown': 'ignore',
            'fbclid': 123,
        }

        self.assertEqual(
            attribution_to_json(attribution),
            json.dumps(
                {
                    'landingPage': 'https://app.example/checkout',
                    'utm_source': 'meta',
                },
                separators=(',', ':'),
                sort_keys=True,
            ),
        )
        self.assertEqual(
            attribution_metadata(attribution),
            {
                'tracking_landingPage': 'https://app.example/checkout',
                'tracking_utm_source': 'meta',
            },
        )


class AbacatePayWebhookSignatureTests(unittest.TestCase):
    def test_validate_webhook_signature_accepts_hmac_signature(self) -> None:
        raw_body = b'{"event":"subscription.completed"}'
        signature = self._signature(raw_body)
        request = SimpleNamespace(headers={'x-webhook-signature': signature})

        with patch.object(settings, 'abacatepay_webhook_signature_key', 'signature-key'):
            _validate_webhook_signature(raw_body, request)

    def test_validate_webhook_signature_accepts_prefixed_alternate_header(self) -> None:
        raw_body = b'{"event":"checkout.completed"}'
        request = SimpleNamespace(
            headers={'x-abacate-signature': f'sha256={self._signature(raw_body)}'}
        )

        with patch.object(settings, 'abacatepay_webhook_signature_key', 'signature-key'):
            _validate_webhook_signature(raw_body, request)

    def test_validate_webhook_signature_rejects_invalid_signature(self) -> None:
        raw_body = b'{"event":"subscription.completed"}'
        request = SimpleNamespace(headers={'x-webhook-signature': 'invalid'})

        with patch.object(settings, 'abacatepay_webhook_signature_key', 'signature-key'):
            with self.assertRaises(HTTPException) as exc_info:
                _validate_webhook_signature(raw_body, request)

        self.assertEqual(exc_info.exception.status_code, 401)

    @staticmethod
    def _signature(raw_body: bytes) -> str:
        return base64.b64encode(
            hmac.new(b'signature-key', raw_body, hashlib.sha256).digest()
        ).decode('ascii')


class UtmifyPayloadTests(unittest.TestCase):
    def test_build_utmify_payload_uses_subscription_and_attribution_data(self) -> None:
        subscription = {
            'external_id': 'cognix.mensal.20260427123456.COGNIX10.tax.email.abc123',
            'plan_id': 'mensal',
            'product_id': 'prod_mensal',
            'attribution_json': attribution_to_json(
                {
                    'utm_source': 'meta',
                    'utm_campaign': 'abril',
                    'xcod': 'criativo-1',
                }
            ),
        }
        webhook_payload = {
            'createdAt': '2026-04-30T12:00:00Z',
            'data': {
                'checkout': {
                    'metadata': {
                        'submittedName': 'Aluno Teste',
                        'submittedEmail': 'aluno@example.com',
                    }
                },
                'payment': {
                    'paidAt': '2026-04-30T12:05:00Z',
                    'method': 'CARD',
                    'customer': {'taxId': '123.***.***-**'},
                },
            },
        }

        with (
            patch.object(settings, 'abacatepay_product_id_mensal', 'prod_mensal'),
            patch.object(settings, 'abacatepay_coupon_mensal_first_month', 'COGNIX10'),
            patch.object(settings, 'utmify_platform', 'Cognix'),
            patch.object(settings, 'utmify_is_test', False),
        ):
            payload = build_utmify_paid_order_payload(subscription, webhook_payload)

        self.assertEqual(payload['orderId'], subscription['external_id'])
        self.assertEqual(payload['status'], 'paid')
        self.assertEqual(payload['paymentMethod'], 'credit_card')
        self.assertEqual(payload['products'][0]['priceInCents'], 1990)
        self.assertEqual(payload['trackingParameters']['utm_source'], 'meta')
        self.assertEqual(payload['trackingParameters']['src'], 'criativo-1')
        self.assertEqual(payload['customer']['email'], 'aluno@example.com')
        self.assertIsNone(payload['customer']['document'])


if __name__ == '__main__':
    unittest.main()
