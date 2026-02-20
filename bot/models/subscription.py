from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, Boolean
from sqlalchemy.orm import relationship
from bot.models.base import Base, TimestampMixin
from datetime import datetime


class Subscription(Base, TimestampMixin):
    __tablename__ = 'subscriptions'

    id = Column(Integer, primary_key=True)

    # Relations
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    user = relationship('User', back_populates='subscriptions')

    # Gateway details
    gateway = Column(String(20), nullable=False)
    gateway_subscription_id = Column(String(255), unique=True, index=True)

    # Plan
    tier = Column(String(20), nullable=False)  # basic, pro, enterprise
    status = Column(String(20), default='active')  # active, canceled, past_due, unpaid

    # Billing
    current_period_start = Column(DateTime)
    current_period_end = Column(DateTime)
    cancel_at_period_end = Column(Boolean, default=False)

    # Amount
    amount = Column(Numeric(10, 2))
    currency = Column(String(3), default='USD')

    # Relations
    payments = relationship('Payment', back_populates='subscription', lazy='dynamic')

    def is_active_now(self):
        return (
            self.status == 'active' and
            self.current_period_end and
            self.current_period_end > datetime.utcnow()
        )

    def __repr__(self):
        return f'<Subscription {self.id} {self.tier} {self.status}>'
