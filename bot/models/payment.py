from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from bot.models.base import Base, TimestampMixin


class Payment(Base, TimestampMixin):
    __tablename__ = 'payments'

    id = Column(Integer, primary_key=True)

    # Relations
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    user = relationship('User', back_populates='payments')
    subscription_id = Column(Integer, ForeignKey('subscriptions.id'), nullable=True)
    subscription = relationship('Subscription', back_populates='payments')

    # Payment details
    gateway = Column(String(20), nullable=False)  # stripe, mercadopago, coinbase
    gateway_payment_id = Column(String(255), unique=True, index=True)
    gateway_customer_id = Column(String(255))

    # Amount
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default='USD')
    fee_amount = Column(Numeric(10, 2), default=0)
    net_amount = Column(Numeric(10, 2))

    # Status
    status = Column(String(20), default='pending')  # pending, completed, failed, refunded
    status_details = Column(Text)

    # Product info
    product_name = Column(String(255))
    product_tier = Column(String(20))
    billing_period = Column(String(20))  # one_time, monthly, yearly

    # Metadata
    raw_webhook_data = Column(JSON)
    receipt_url = Column(String(500))
    invoice_pdf = Column(String(500))

    def __repr__(self):
        return f'<Payment {self.id} {self.amount} {self.currency} {self.status}>'
