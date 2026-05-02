"""
Analytics service — business logic for computing analytics.
No HTTP concepts.
"""

import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional

from app.core.exceptions import NotFoundError
from app.core.pagination import paginate
from app.features.chat.repository import (
    fetch_all_messages_by_company,
    fetch_all_chats_by_company,
    fetch_guest_chats_paginated,
    fetch_messages_for_chats,
    fetch_messages,
    get_chat_by_id,
)
from app.features.users.repository import (
    fetch_all_users_by_company,
    fetch_all_guest_sessions_by_company,
    fetch_guest_sessions_by_ids,
    get_guest_session,
)
from app.features.documents.repository import fetch_all_knowledge_bases_by_company
from app.features.analytics.schemas import (
    ChangeIndicator,
    OverviewCard,
    MessagesTimePoint,
    ChatsTimePoint,
    UserWithStats,
    OverviewStats,
    TimeSeries,
    AnalyticsMetadata,
    AnalyticsDashboard,
    CompanyUsersResponse,
    ConversationListItem,
    ConversationsListResponse,
    TranscriptMessage,
    ConversationDetail,
)


def _calculate_change(current: int, previous: int) -> ChangeIndicator:
    if previous == 0:
        if current == 0:
            return ChangeIndicator(value="0%", type="neutral")
        return ChangeIndicator(value="+100%", type="increase")
    change_percent = ((current - previous) / previous) * 100
    if change_percent > 0:
        return ChangeIndicator(value=f"+{change_percent:.1f}%", type="increase")
    if change_percent < 0:
        return ChangeIndicator(value=f"{change_percent:.1f}%", type="decrease")
    return ChangeIndicator(value="0%", type="neutral")


def _count_records_in_period(
    records: List[Dict], start_date: datetime, end_date: Optional[datetime] = None
) -> int:
    count = 0
    for record in records:
        created_at_str = record.get("created_at")
        if not created_at_str:
            continue
        try:
            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        except Exception:
            continue
        if end_date:
            if start_date <= created_at < end_date:
                count += 1
        elif created_at >= start_date:
            count += 1
    return count


def get_dashboard_analytics(company_id: str) -> AnalyticsDashboard:
    start_time = time.time()
    tz = timezone.utc
    now = datetime.now(tz)
    last_7_days = now - timedelta(days=7)
    last_14_days = now - timedelta(days=14)

    all_messages = fetch_all_messages_by_company(company_id)
    all_users = fetch_all_users_by_company(company_id)
    all_chats = fetch_all_chats_by_company(company_id)
    all_kbs = fetch_all_knowledge_bases_by_company(company_id)
    all_sessions = fetch_all_guest_sessions_by_company(company_id)

    current_messages = _count_records_in_period(all_messages, last_7_days)
    previous_messages = _count_records_in_period(all_messages, last_14_days, last_7_days)
    current_users = _count_records_in_period(all_users, last_7_days)
    previous_users = _count_records_in_period(all_users, last_14_days, last_7_days)
    current_chats = _count_records_in_period(all_chats, last_7_days)
    previous_chats = _count_records_in_period(all_chats, last_14_days, last_7_days)
    current_kb = _count_records_in_period(all_kbs, last_7_days)
    previous_kb = _count_records_in_period(all_kbs, last_14_days, last_7_days)
    current_guest = _count_records_in_period(all_sessions, last_7_days)
    previous_guest = _count_records_in_period(all_sessions, last_14_days, last_7_days)

    overview = OverviewStats(
        totalMessages=OverviewCard(count=current_messages, change=_calculate_change(current_messages, previous_messages)),
        users=OverviewCard(count=current_users, change=_calculate_change(current_users, previous_users)),
        totalChats=OverviewCard(count=current_chats, change=_calculate_change(current_chats, previous_chats)),
        knowledgeBases=OverviewCard(count=current_kb, change=_calculate_change(current_kb, previous_kb)),
        guestSessions=OverviewCard(count=current_guest, change=_calculate_change(current_guest, previous_guest)),
    )

    messages_over_time = []
    chats_over_time = []
    for i in range(7):
        target_date = now.date() - timedelta(days=i)
        day_start = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=tz)
        day_end = day_start + timedelta(days=1)
        day_str = target_date.strftime("%Y-%m-%d")
        messages_over_time.append(MessagesTimePoint(
            date=day_str, totalMessages=_count_records_in_period(all_messages, day_start, day_end),
        ))
        chats_over_time.append(ChatsTimePoint(
            date=day_str, newChats=_count_records_in_period(all_chats, day_start, day_end),
        ))

    messages_over_time.reverse()
    chats_over_time.reverse()

    query_time = time.time() - start_time
    metadata = AnalyticsMetadata(
        lastUpdated=now.isoformat(),
        queryExecutionTime=round(query_time, 3),
        companyId=company_id,
    )

    return AnalyticsDashboard(
        overview=overview,
        timeSeries=TimeSeries(messagesOverTime=messages_over_time, chatsOverTime=chats_over_time),
        metadata=metadata,
    )


def get_company_users_with_stats(
    company_id: str, page: int = 1, page_size: int = 20
) -> CompanyUsersResponse:
    all_users = fetch_all_users_by_company(company_id)
    all_chats = fetch_all_chats_by_company(company_id)
    all_messages = fetch_all_messages_by_company(company_id)

    # Build lookup sets for O(n) instead of O(n*m)
    user_chat_map: Dict[str, List[str]] = {}
    for chat in all_chats:
        uid = chat.get("user_id")
        if uid:
            user_chat_map.setdefault(uid, []).append(chat["chat_id"])

    chat_message_count: Dict[str, int] = {}
    for msg in all_messages:
        cid = msg.get("chat_id")
        if cid:
            chat_message_count[cid] = chat_message_count.get(cid, 0) + 1

    users_with_stats = []
    total_chats = 0
    total_messages = 0

    for user_data in all_users:
        user_id = user_data["user_id"]
        is_anonymous = user_data.get("is_anonymous", False)
        user_chats = user_chat_map.get(user_id, [])
        chat_count = len(user_chats)
        message_count = sum(chat_message_count.get(cid, 0) for cid in user_chats)

        if not is_anonymous:
            total_chats += chat_count
            total_messages += message_count

        users_with_stats.append(UserWithStats(
            user_id=user_id,
            email=user_data.get("email"),
            name=user_data.get("name"),
            is_anonymous=is_anonymous,
            chat_count=chat_count,
            message_count=message_count,
            created_at=user_data.get("created_at", ""),
        ))

    users_with_stats.sort(key=lambda u: u.created_at, reverse=True)
    result = paginate(users_with_stats, page, page_size)

    return CompanyUsersResponse(
        users=result["items"],
        total_users=result["total"],
        total_chats=total_chats,
        total_messages=total_messages,
        company_id=company_id,
        page=result["page"],
        page_size=result["page_size"],
        total_pages=result["total_pages"],
    )


_PREVIEW_CHARS = 120


def _ms_to_iso(ms: Optional[int]) -> Optional[str]:
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def get_company_conversations(
    company_id: str, page: int = 1, page_size: int = 25
) -> ConversationsListResponse:
    page_data = fetch_guest_chats_paginated(company_id, page=page, page_size=page_size)
    chats: List[Dict[str, Any]] = page_data["items"]

    chat_ids = [c["chat_id"] for c in chats]
    session_ids = [c["session_id"] for c in chats if c.get("session_id")]

    messages = fetch_messages_for_chats(company_id, chat_ids)
    sessions = fetch_guest_sessions_by_ids(company_id, session_ids)
    sessions_by_id = {s["session_id"]: s for s in sessions}

    msgs_by_chat: Dict[str, List[Dict[str, Any]]] = {}
    for m in messages:
        msgs_by_chat.setdefault(m["chat_id"], []).append(m)

    items: List[ConversationListItem] = []
    for chat in chats:
        chat_msgs = msgs_by_chat.get(chat["chat_id"], [])
        first_user = next((m for m in chat_msgs if m.get("role") == "human"), None)
        preview = (first_user or {}).get("content", "") or ""
        if len(preview) > _PREVIEW_CHARS:
            preview = preview[:_PREVIEW_CHARS].rstrip() + "…"

        last_ts = max((m.get("timestamp") for m in chat_msgs if m.get("timestamp") is not None), default=None)
        session = sessions_by_id.get(chat.get("session_id")) if chat.get("session_id") else None

        items.append(ConversationListItem(
            chat_id=chat["chat_id"],
            session_id=chat.get("session_id"),
            started_at=chat.get("created_at", ""),
            last_message_at=_ms_to_iso(last_ts),
            message_count=len(chat_msgs),
            preview=preview,
            ip_address=(session or {}).get("ip_address"),
        ))

    return ConversationsListResponse(
        conversations=items,
        total=page_data["total"],
        page=page_data["page"],
        page_size=page_data["page_size"],
        total_pages=page_data["total_pages"],
    )


def get_conversation_detail(company_id: str, chat_id: str) -> ConversationDetail:
    chat = get_chat_by_id(chat_id)
    if not chat or chat.get("company_id") != company_id or not chat.get("is_guest"):
        raise NotFoundError("Conversation not found")

    raw_messages = fetch_messages(company_id, chat_id)
    transcript = [
        TranscriptMessage(
            role=m.get("role", ""),
            content=m.get("content", ""),
            timestamp=m.get("timestamp") or 0,
        )
        for m in raw_messages
    ]

    session = get_guest_session(chat["session_id"]) if chat.get("session_id") else None

    return ConversationDetail(
        chat_id=chat_id,
        session_id=chat.get("session_id"),
        started_at=chat.get("created_at", ""),
        ip_address=(session or {}).get("ip_address"),
        user_agent=(session or {}).get("user_agent"),
        messages=transcript,
        message_count=len(transcript),
    )
