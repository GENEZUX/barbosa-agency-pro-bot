import os
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class Config:
    # Telegram
    TELEGRAM_TOKEN: str = os.getenv('TELEGRAM_TOKEN', '')
    ADMIN_USER_IDS: List[int] = None

    # Database
    DATABASE_URL: str = os.getenv('DATABASE_URL', 'postgresql://localhost/barbosa')
    REDIS_URL: str = os.getenv('REDIS_URL', 'redis://localhost:6379')

    # Stripe Global
    STRIPE_SECRET_KEY: str = os.getenv('STRIPE_SECRET_KEY', '')
    STRIPE_WEBHOOK_SECRET: str = os.getenv('STRIPE_WEBHOOK_SECRET', '')
    STRIPE_PUBLISHABLE_KEY: str = os.getenv('STRIPE_PUBLISHABLE_KEY', '')

    # Stripe Products
    STRIPE_PRICE_BASIC: str = os.getenv('STRIPE_PRICE_BASIC', '')
    STRIPE_PRICE_PRO: str = os.getenv('STRIPE_PRICE_PRO', '')
    STRIPE_PRICE_ENTERPRISE: str = os.getenv('STRIPE_PRICE_ENTERPRISE', '')

    # MercadoPago Latinoamerica
    MP_ACCESS_TOKEN: str = os.getenv('MP_ACCESS_TOKEN', '')
    MP_PUBLIC_KEY: str = os.getenv('MP_PUBLIC_KEY', '')
    MP_WEBHOOK_SECRET: str = os.getenv('MP_WEBHOOK_SECRET', '')

    # Coinbase Commerce Crypto
    COINBASE_API_KEY: str = os.getenv('COINBASE_API_KEY', '')
    COINBASE_WEBHOOK_SECRET: str = os.getenv('COINBASE_WEBHOOK_SECRET', '')

    # Web App
    SECRET_KEY: str = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-prod')
    BASE_URL: str = os.getenv('RAILWAY_PUBLIC_DOMAIN', 'http://localhost:5000')

    # Feature Flags
    ENABLE_STRIPE: bool = os.getenv('ENABLE_STRIPE', 'true').lower() == 'true'
    ENABLE_MP: bool = os.getenv('ENABLE_MP', 'true').lower() == 'true'
    ENABLE_CRYPTO: bool = os.getenv('ENABLE_CRYPTO', 'false').lower() == 'true'

    # Notifications
    SENTRY_DSN: Optional[str] = os.getenv('SENTRY_DSN')
    ALERT_EMAIL: str = os.getenv('ALERT_EMAIL', 'admin@barbosa.agency')

    def __post_init__(self):
        if self.ADMIN_USER_IDS is None:
            admin_ids = os.getenv('ADMIN_USER_IDS', '')
            self.ADMIN_USER_IDS = [int(x.strip()) for x in admin_ids.split(',') if x.strip()]
        if not self.BASE_URL.startswith('http'):
            self.BASE_URL = f'https://{self.BASE_URL}'


config = Config()
