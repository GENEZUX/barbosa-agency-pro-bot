from sqlalchemy import Column, Integer, String, BigInteger, DateTime, JSON, Boolean
from sqlalchemy.orm import relationship
from bot.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    email = Column(String(255), unique=True)
    phone = Column(String(50))

    # Metadata
    language_code = Column(String(10), default='es')
    timezone = Column(String(50), default='America/Puerto_Rico')

    # Subscription status
    subscription_tier = Column(String(20), default='free')  # free, basic, pro, enterprise
    subscription_status = Column(String(20), default='inactive')  # active, canceled, past_due
    subscription_expires_at = Column(DateTime)

    # Payment preferences
    preferred_gateway = Column(String(20), default='stripe')  # stripe, mp, crypto

    # Relations
    payments = relationship('Payment', back_populates='user', lazy='dynamic')
    subscriptions = relationship('Subscription', back_populates='user', lazy='dynamic')

    # Admin
    is_admin = Column(Boolean, default=False)
    admin_notes = Column(JSON, default=dict)

    def __repr__(self):
        return f'<User {self.telegram_id} @{self.username}>'

    def to_dict(self):
        return {
            'id': self.id,
            'telegram_id': self.telegram_id,
            'username': self.username,
            'email': self.email,
            'subscription_tier': self.subscription_tier,
            'subscription_status': self.subscription_status,
            'is_active': self.is_active
        }
