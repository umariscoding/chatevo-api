"""
Billing repository — database operations for subscription state.

All functions are synchronous (matching the Supabase SDK pattern).
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional

from app.core.database import db, generate_id


# ---------------------------------------------------------------------------
# Webhook event logging & idempotency
# ---------------------------------------------------------------------------

def is_webhook_processed(event_id: str) -> bool:
    """Check if a webhook event has already been processed (idempotency)."""
    res = (
        db.table("webhook_events")
        .select("id")
        .eq("event_id", event_id)
        .execute()
    )
    return bool(res.data)


def log_webhook_event(
    event_id: str,
    event_name: str,
    company_id: Optional[str],
    ls_subscription_id: Optional[str],
    processed: bool = True,
    error: Optional[str] = None,
) -> None:
    """Insert a webhook event record for audit trail."""
    db.table("webhook_events").insert({
        "id": generate_id(),
        "event_id": event_id,
        "event_name": event_name,
        "company_id": company_id,
        "ls_subscription_id": ls_subscription_id,
        "processed": processed,
        "error": error,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()


# ---------------------------------------------------------------------------
# Subscription operations
# ---------------------------------------------------------------------------

def update_subscription(
    company_id: str,
    ls_customer_id: Optional[str] = None,
    ls_subscription_id: Optional[str] = None,
    ls_subscription_status: Optional[str] = None,
    plan: Optional[str] = None,
    subscription_ends_at: Optional[str] = None,
    subscription_renews_at: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Update company subscription fields after a webhook event."""
    update_data: Dict[str, Any] = {}

    if ls_customer_id is not None:
        update_data["ls_customer_id"] = ls_customer_id
    if ls_subscription_id is not None:
        update_data["ls_subscription_id"] = ls_subscription_id
    if ls_subscription_status is not None:
        update_data["ls_subscription_status"] = ls_subscription_status
    if plan is not None:
        update_data["plan"] = plan
    if subscription_ends_at is not None:
        update_data["subscription_ends_at"] = subscription_ends_at
    if subscription_renews_at is not None:
        update_data["subscription_renews_at"] = subscription_renews_at

    if not update_data:
        return None

    res = db.table("companies").update(update_data).eq("company_id", company_id).execute()
    return res.data[0] if res.data else None


def get_company_by_ls_subscription_id(ls_subscription_id: str) -> Optional[Dict[str, Any]]:
    """Look up a company by LemonSqueezy subscription ID (for webhook processing)."""
    res = (
        db.table("companies")
        .select("*")
        .eq("ls_subscription_id", ls_subscription_id)
        .execute()
    )
    return res.data[0] if res.data else None


def get_company_subscription(company_id: str) -> Optional[Dict[str, Any]]:
    """Get subscription-related fields for a company."""
    res = (
        db.table("companies")
        .select(
            "plan, ls_customer_id, ls_subscription_id, ls_subscription_status, "
            "subscription_ends_at, subscription_renews_at"
        )
        .eq("company_id", company_id)
        .execute()
    )
    return res.data[0] if res.data else None


