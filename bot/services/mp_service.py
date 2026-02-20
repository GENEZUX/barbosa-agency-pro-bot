import mercadopago
from typing import Dict, Optional
from bot.utils.config import config
from bot.models.user import User
from bot.models.payment import Payment
from bot.models.base import db_session

mp = mercadopago.SDK(config.MP_ACCESS_TOKEN)


class MercadoPagoService:
    TIER_PRICES = {
        'basic': 9.00,
        'pro': 29.00,
        'enterprise': 99.00
    }

    @staticmethod
    def create_preference(user: User, tier: str) -> Dict:
        price = MercadoPagoService.TIER_PRICES.get(tier, 9.00)
        preference_data = {
            'items': [{
                'title': f'Barbosa Agency - Plan {tier.capitalize()}',
                'quantity': 1,
                'unit_price': price,
                'currency_id': 'USD'
            }],
            'payer': {
                'name': user.first_name or 'Cliente',
                'surname': user.last_name or '',
                'email': user.email or f'{user.telegram_id}@barbosa.agency'
            },
            'back_urls': {
                'success': f'{config.BASE_URL}/mp/success',
                'failure': f'{config.BASE_URL}/mp/failure',
                'pending': f'{config.BASE_URL}/mp/pending'
            },
            'auto_return': 'approved',
            'external_reference': f'{user.id}|{tier}',
            'notification_url': f'{config.BASE_URL}/webhook/mercadopago',
            'metadata': {
                'user_id': user.id,
                'telegram_id': user.telegram_id,
                'tier': tier
            }
        }
        preference_response = mp.preference().create(preference_data)
        return preference_response['response']

    @staticmethod
    def process_webhook(data: Dict) -> Optional[Payment]:
        payment_id = data.get('data', {}).get('id')
        if not payment_id:
            return None

        payment_info = mp.payment().get(payment_id)
        payment_data = payment_info['response']
        status = payment_data.get('status')
        external_ref = payment_data.get('external_reference', '')

        if '|' in external_ref:
            user_id, tier = external_ref.split('|')
            user_id = int(user_id)
        else:
            return None

        user = User.query.get(user_id)
        if not user:
            return None

        payment = Payment(
            user_id=user.id,
            gateway='mercadopago',
            gateway_payment_id=str(payment_id),
            amount=float(payment_data.get('transaction_details', {}).get('total_paid_amount', 0)),
            currency='USD',
            status='completed' if status == 'approved' else 'pending',
            product_tier=tier,
            billing_period='one_time',
            raw_webhook_data=payment_data
        )

        if status == 'approved':
            user.subscription_tier = tier
            user.subscription_status = 'active'

        db_session.add(payment)
        db_session.commit()
        return payment
