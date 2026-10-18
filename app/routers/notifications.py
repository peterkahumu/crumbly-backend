import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Notification, User
from app.schemas.notification import NotificationResponse

router = APIRouter(prefix="/notifications", tags=["notifications"])

# Global event bus for real-time notifications
# In a multi-worker production setup, you would use Redis Pub/Sub here.
# For simplicity in this local migration, we'll use an in-memory queue per connected user.
_user_queues: dict[str, list[asyncio.Queue]] = {}


def notify_user_realtime(user_id: str, notification: dict):
    if user_id in _user_queues:
        for q in _user_queues[user_id]:
            q.put_nowait(notification)


@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.scalar(
        select(func.count(Notification.id))
        .where(Notification.user_id == current_user.id, Notification.is_read == False)
    )
    return {"count": result or 0}


@router.patch("/{notif_id}/read")
async def mark_read(
    notif_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    notif = await db.scalar(
        select(Notification).where(Notification.id == notif_id, Notification.user_id == current_user.id)
    )
    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
        
    notif.is_read = True
    await db.commit()
    
    return {"success": True}


@router.patch("/read-all")
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_read == False)
        .values(is_read=True)
    )
    await db.commit()
    
    return {"success": True}


@router.get("/stream")
async def notification_stream(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Server-Sent Events endpoint for real-time notifications."""
    
    # Create a queue for this connection
    q = asyncio.Queue()
    
    if current_user.id not in _user_queues:
        _user_queues[current_user.id] = []
    _user_queues[current_user.id].append(q)
    
    async def event_generator():
        try:
            while True:
                # If client disconnected, break
                if await request.is_disconnected():
                    break
                    
                # Wait for a new notification in the queue
                try:
                    notif_data = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield {
                        "event": "message",
                        "data": json.dumps(notif_data)
                    }
                except asyncio.TimeoutError:
                    # Send a keep-alive ping
                    yield {
                        "event": "ping",
                        "data": "keep-alive"
                    }
        finally:
            # Cleanup on disconnect
            if current_user.id in _user_queues:
                if q in _user_queues[current_user.id]:
                    _user_queues[current_user.id].remove(q)
                if not _user_queues[current_user.id]:
                    del _user_queues[current_user.id]
                    
    return EventSourceResponse(event_generator())
