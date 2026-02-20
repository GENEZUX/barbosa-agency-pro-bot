import stripe
from typing import Dict, Optional, Tuple
from bot.utils.config import config
from bot.models.user import User
from bot.models.payment import Payment
from bot.models.subscription import Subscription
from bot.models.base import db_session
from datetime import datetime

stripe.api_key = config.STRIPE_SECRET_KEY


class StripeService:
    TIER_PRICES = {
        'basic': config.STRIPE_PRICE_BASIC,
        'pro': config.STRIPE_PRICE_PRO,
        'enterprise': config.STRIPE_PRICE_ENTERPRISE
    }
    TIER_AMOUNTS = {
        'basic': 9.00,
        'pro': 29.00,
        'enterprise': 99.00
    }

    @staticmethod
    def create_customer(user: User) -> str:
        customer = stripe.Customer.create(
            email=user.email or f'{user.telegram_id}@barbosa.agency',
            name=f'{user.first_name or ""} {user.last_name or ""}'.strip(),
            metadata={
                'telegram_id': user.telegram_id,
                'user_id': user.id,
                'username': user.username or 'unknown'
            }
        )
        return customer.id

    @staticmethod
    def create_checkout_session(user: User, tier: str, mode: str = 'subscription') -> Dict:
        price_id = StripeService.TIER_PRICES.get(tier)
        if not price_id:
            raise ValueError(f'Tier {tier} no valido')

        customer_id = None
        existing_payment = user.payments.first()
        if existing_payment and existing_payment.gateway_customer_id:
            customer_id = existing_payment.gateway_customer_id
        else:
            customer_id = StripeService.create_customer(user)

        success_url = f'{config.BASE_URL}/payment/success?session_id={{CHECKOUT_SESSION_ID}}'
        cancel_url = f'{config.BASE_URL}/payment/cancel'

        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            line_items=[{'price': price_id, 'quantity': 1}],
            mode=mode,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                'user_id': str(user.id),
                'telegram_id': str(user.telegram_id),
                'tier': tier,
                'gateway': 'stripe'
            },
            subscription_data={
                'metadata': {'user_id': str(user.id), 'tier': tier}
            } if mode == 'subscription' else None,
            allow_promotion_codes=True,
            billing_address_collection='auto',
        )
        return {'session_id': session.id, 'url': session.url, 'customer_id': customer_id}

    @staticmethod
    def process_webhook(payload: bytes, sig_header: str) -> Tuple[str, Optional[Dict]]:
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, config.STRIPE_WEBHOOK_SECRET
            )
        except ValueError:
            return 'invalid_payload', None
        except stripe.error.SignatureVerificationError:
            return 'invalid_signature', None

        event_type = event['type']
        data = event['data']['object']

        if event_type == 'checkout.session.completed':
            StripeService._handle_checkout_completed(data)
        elif event_type == 'invoice.payment_succeeded':
            StripeService._handle_invoice_paid(data)
        elif event_type == 'invoice.payment_failed':
            StripeService._handle_payment_failed(data)
        elif event_type == 'customer.subscription.deleted':
            StripeService._handle_subscription_cancelled(data)
        elif event_type == 'customer.subscription.updated':
            StripeService._handle_subscription_updated(data)

        return 'success', {'type': event_type, 'id': data.get('id')}

    @staticmethod
    def _handle_checkout_completed(data: Dict):
        metadata = data.get('metadata', {})
        user_id = int(metadata.get('user_id', 0))
        tier = metadata.get('tier', 'basic')
        user = User.query.get(user_id)
        if not user:
            return

        payment = Payment(
            user_id=user.id,
            gateway='stripe',
            gateway_payment_id=data.get('payment_intent') or data['id'],
            gateway_customer_id=data.get('customer'),
            amount=float(data['amount_total']) / 100,
            currency=data['currency'].upper(),
            status='completed',
            product_tier=tier,
            billing_period='monthly' if data.get('subscription') else 'one_time',
            raw_webhook_data=data
        )

        if data.get('subscription'):
            subscription = Subscription(
                user_id=user.id,
                gateway='stripe',
                gateway_subscription_id=data['subscription'],
                tier=tier,
                status='active',
                amount=StripeService.TIER_AMOUNTS.get(tier, 0),
                currency=data['currency'].upper()
            )
            db_session.add(subscription)
            payment.subscription = subscription

        user.subscription_tier = tier
        user.subscription_status = 'active'
        db_session.add(payment)
        db_session.commit()

    @staticmethod
    def _handle_invoice_paid(data: Dict):
        subscription_id = data.get('subscription')
        subscription = Subscription.query.filter_by(
            gateway_subscription_id=subscription_id
        ).first()
        if subscription:
            payment = Payment(
                user_id=subscription.user_id,
                subscription_id=subscription.id,
                gateway='stripe',
                gateway_payment_id=data.get('payment_intent'),
                amount=float(data['amount_paid']) / 100,
                currency=data['currency'].upper(),
                status='completed',
                product_tier=subscription.tier,
                billing_period='monthly',
                raw_webhook_data=data
            )
            db_session.add(payment)
            subscription.current_period_start = datetime.fromtimestamp(data['period_start'])
            subscription.current_period_end = datetime.fromtimestamp(data['period_end'])
            db_session.commit()

    @staticmethod
    def _handle_payment_failed(data: Dict):
        subscription_id = data.get('subscription')
        subscription = Subscription.query.filter_by(
            gateway_subscription_id=subscription_id
        ).first()
        if subscription:
            subscription.status = 'past_due'
            subscription.user.subscription_status = 'past_due'
            db_session.commit()

    @staticmethod
    def _handle_subscription_cancelled(data: Dict):
        subscription = Subscription.query.filter_by(
            gateway_subscription_id=data['id']
        ).first()
        if subscription:
            subscription.status = 'canceled'
            subscription.user.subscription_tier = 'free'
            subscription.user.subscription_status = 'inactive'
            subscription.is_active = False
            db_session.commit()

    @staticmethod
    def _handle_subscription_updated(data: Dict):
        subscription = Subscription.query.filter_by(
            gateway_subscription_id=data['id']
        ).first()
        if subscription:
            subscription.status = data.get('status', subscription.status)
            if data.get('current_period_end'):
                subscription.current_period_end = datetime.fromtimestamp(data['current_period_end'])
            db_session.commit()
