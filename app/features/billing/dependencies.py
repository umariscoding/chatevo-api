"""
Billing dependencies — plan-based access control for FastAPI endpoints.
"""

from fastapi import Depends, HTTPException, status

from app.features.auth.dependencies import get_current_company, UserContext
from app.features.auth.repository import get_company_by_id
from app.features.billing.service import is_plan_active


async def require_pro_plan(
    current_company: UserContext = Depends(get_current_company),
) -> UserContext:
    """Dependency that rejects requests from free-plan companies.

    Checks both the plan field AND subscription status/dates so that
    expired or cancelled-past-end-date subscriptions are correctly denied.
    """
    company = get_company_by_id(current_company.company_id)
    if not company or not is_plan_active(company):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This feature requires a Pro plan. Please upgrade to continue.",
        )
    return current_company
