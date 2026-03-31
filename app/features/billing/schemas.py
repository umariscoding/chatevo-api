"""
Billing schemas — request/response models for subscription management.
"""

from pydantic import BaseModel
from typing import Optional


class CheckoutResponse(BaseModel):
    checkout_url: str


class SubscriptionStatusResponse(BaseModel):
    plan: str
    ls_subscription_status: str
    subscription_ends_at: Optional[str] = None
    subscription_renews_at: Optional[str] = None
    manage_url: Optional[str] = None
