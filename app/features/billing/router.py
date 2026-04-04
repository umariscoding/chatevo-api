"""
Billing router — HTTP endpoints for subscription management.

Mounted at /billing.
"""

import logging

from fastapi import APIRouter, Request, Depends

from app.core.exceptions import AuthorizationError
from app.features.auth.dependencies import get_current_company, UserContext
from app.features.billing import service
from app.features.billing.schemas import CheckoutResponse, SubscriptionStatusResponse

logger = logging.getLogger("botbeetle.billing")

router = APIRouter(prefix="/billing", tags=["billing"])


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    current_company: UserContext = Depends(get_current_company),
):
    """Generate a LemonSqueezy checkout URL for upgrading to Pro."""
    url = service.create_checkout_url(
        company_id=current_company.company_id,
        email=current_company.email,
    )
    return CheckoutResponse(checkout_url=url)


@router.get("/subscription", response_model=SubscriptionStatusResponse)
async def get_subscription(
    current_company: UserContext = Depends(get_current_company),
):
    """Get current subscription status."""
    return service.get_subscription_status(current_company.company_id)


@router.post("/cancel")
async def cancel_subscription(
    current_company: UserContext = Depends(get_current_company),
):
    """Cancel the current subscription (effective at end of billing period)."""
    return service.cancel_subscription(current_company.company_id)


@router.post("/resume")
async def resume_subscription(
    current_company: UserContext = Depends(get_current_company),
):
    """Resume a cancelled subscription during the grace period."""
    return service.resume_subscription(current_company.company_id)


@router.post("/webhook")
async def webhook(request: Request):
    """LemonSqueezy webhook endpoint. No auth — verified via HMAC signature.

    Returns 200 on success or duplicate (idempotent).
    Returns 401 on invalid signature (prevents retries).
    Returns 500 on processing errors (allows LemonSqueezy to retry).
    """
    raw_body = await request.body()
    signature = request.headers.get("x-signature", "")

    try:
        service.handle_webhook(raw_body, signature)
    except AuthorizationError:
        logger.warning("Webhook rejected: invalid signature")
        raise  # 401 — don't retry
    except Exception:
        logger.exception("Webhook processing failed")
        raise  # 500 — LemonSqueezy will retry

    return {"status": "ok"}
