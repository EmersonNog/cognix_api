from sqlalchemy import Column, Index, String, Table, Text, UniqueConstraint

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
