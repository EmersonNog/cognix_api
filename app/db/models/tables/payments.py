from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)

from ..common import _id_column, _timestamp_columns, metadata


def get_coupon_redemptions_table(table_name: str) -> Table:
    return Table(
        table_name,
        metadata,
        _id_column(),
        Column('coupon_code', String(64), nullable=False),
        Column('tax_id_hash', String(64), nullable=False),
        Column('email_hash', String(64), nullable=False),
        Column('plan_id', String(64), nullable=False),
        Column('product_id', String(255), nullable=False),
        Column('checkout_id', String(255), nullable=True),
        Column('checkout_url', Text, nullable=True),
        Column('external_id', String(255), nullable=False, unique=True),
        Column('status', String(64), nullable=False, default='pending_checkout'),
        *_timestamp_columns(),
        UniqueConstraint(
            'coupon_code',
            'tax_id_hash',
            name=f'uq_{table_name}_coupon_tax_id',
        ),
        UniqueConstraint(
            'coupon_code',
            'email_hash',
            name=f'uq_{table_name}_coupon_email',
        ),
        Index(f'ix_{table_name}_coupon_status', 'coupon_code', 'status'),
        extend_existing=True,
    )


def get_payment_subscriptions_table(table_name: str) -> Table:
    return Table(
        table_name,
        metadata,
        _id_column(),
        Column('user_id', Integer, nullable=True, index=True),
        Column('firebase_uid', String(255), nullable=True, index=True),
        Column('email_hash', String(64), nullable=False, index=True),
        Column('tax_id_hash', String(64), nullable=False),
        Column('plan_id', String(64), nullable=False),
        Column('product_id', String(255), nullable=False),
        Column('external_customer_id', String(255), nullable=True),
        Column('external_subscription_id', String(255), nullable=True, index=True),
        Column('checkout_id', String(255), nullable=True),
        Column('checkout_url', Text, nullable=True),
        Column('external_id', String(255), nullable=False, unique=True),
        Column('status', String(64), nullable=False, default='checkout_created'),
        Column('current_period_ends_at', DateTime(timezone=True), nullable=True),
        Column('cancel_requested_at', Text, nullable=True),
        Column('cancelled_at', Text, nullable=True),
        *_timestamp_columns(),
        Index(f'ix_{table_name}_email_status', 'email_hash', 'status'),
        Index(f'ix_{table_name}_user_status', 'user_id', 'status'),
        extend_existing=True,
    )


def get_google_play_subscriptions_table(table_name: str) -> Table:
    return Table(
        table_name,
        metadata,
        _id_column(),
        Column('user_id', Integer, nullable=False, index=True),
        Column('firebase_uid', String(255), nullable=False, index=True),
        Column('email_hash', String(64), nullable=True, index=True),
        Column('package_name', String(255), nullable=False),
        Column('product_id', String(255), nullable=False, index=True),
        Column('purchase_token', Text, nullable=False),
        Column('latest_order_id', String(255), nullable=True, index=True),
        Column('base_plan_id', String(255), nullable=True),
        Column('offer_id', String(255), nullable=True),
        Column('status', String(64), nullable=False, default='active'),
        Column('subscription_state', String(128), nullable=True),
        Column('acknowledgement_state', String(128), nullable=True),
        Column('auto_renewing', Boolean, nullable=True),
        Column('current_period_ends_at', DateTime(timezone=True), nullable=True),
        Column('raw_payload', Text, nullable=True),
        *_timestamp_columns(),
        UniqueConstraint(
            'purchase_token',
            name=f'uq_{table_name}_purchase_token',
        ),
        Index(f'ix_{table_name}_user_status', 'user_id', 'status'),
        Index(f'ix_{table_name}_firebase_status', 'firebase_uid', 'status'),
        extend_existing=True,
    )
