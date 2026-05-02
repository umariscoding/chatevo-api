"""
Analytics router — thin HTTP layer for analytics endpoints.
"""

from fastapi import APIRouter, Depends

from app.features.auth.dependencies import get_current_company, UserContext
from app.features.billing.dependencies import require_pro_plan
from app.features.analytics import service
from app.features.analytics.schemas import (
    AnalyticsDashboard,
    CompanyUsersResponse,
    ConversationsListResponse,
    ConversationDetail,
)

router = APIRouter(prefix="/api/company/analytics", tags=["analytics"])


@router.get("/dashboard")
def get_dashboard_analytics(
    user: UserContext = Depends(get_current_company),
) -> AnalyticsDashboard:
    return service.get_dashboard_analytics(user.company_id)


@router.get("/users")
def get_company_users_with_stats(
    page: int = 1,
    page_size: int = 20,
    user: UserContext = Depends(require_pro_plan),
) -> CompanyUsersResponse:
    return service.get_company_users_with_stats(user.company_id, page=page, page_size=page_size)


@router.get("/conversations")
def get_company_conversations(
    page: int = 1,
    page_size: int = 25,
    user: UserContext = Depends(get_current_company),
) -> ConversationsListResponse:
    return service.get_company_conversations(user.company_id, page=page, page_size=page_size)


@router.get("/conversations/{chat_id}")
def get_conversation_detail(
    chat_id: str,
    user: UserContext = Depends(get_current_company),
) -> ConversationDetail:
    return service.get_conversation_detail(user.company_id, chat_id)
