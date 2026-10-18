from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import time
from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Bakery, Conversation, Message, Order, Role, SenderType, User
from app.schemas.messaging import (
    ConversationCreate,
    ConversationResponse,
    CustomerConversationCreate,
    MessageCreate,
    MessageResponse,
    TypingStatusResponse,
    TypingStatusUpdate,
)

router = APIRouter(prefix="/messaging", tags=["messaging"])

# In-memory real-time typing tracker: conv_id -> {"sender_type": str, "sender_name": str, "expires_at": float}
_typing_state: dict[str, dict] = {}


def _get_typing_status(conv_id: str, exclude_sender_type: str | None = None) -> tuple[bool, str | None]:
    state = _typing_state.get(conv_id)
    if state and state["expires_at"] > time.time():
        if exclude_sender_type is None or state["sender_type"] != exclude_sender_type:
            return True, state["sender_name"]
    return False, None



@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Conversation)
        .options(selectinload(Conversation.messages), selectinload(Conversation.bakery))
        .order_by(Conversation.updated_at.desc())
    )

    if current_user.role == Role.BAKER.value:
        if not current_user.bakery:
            return []
        query = query.where(Conversation.bakery_id == current_user.bakery.id)

    result = await db.execute(query)
    convs = result.scalars().all()

    responses = []
    for c in convs:
        resp = ConversationResponse.model_validate(c)
        if c.bakery:
            resp.bakeryName = c.bakery.name
            resp.bakerySlug = c.bakery.slug

        if c.messages:
            sorted_msgs = sorted(c.messages, key=lambda m: m.created_at)
            resp.lastMessage = sorted_msgs[-1].content
            if current_user.role == Role.BAKER.value:
                resp.unreadCount = sum(1 for m in c.messages if not m.is_read and m.sender_type != SenderType.BAKER.value)
            elif current_user.role == Role.SUPER_ADMIN.value:
                resp.unreadCount = sum(1 for m in c.messages if not m.is_read and m.sender_type != SenderType.ADMIN.value)

        if c.order_id:
            order = await db.scalar(select(Order).where(Order.id == c.order_id))
            if order:
                resp.customerName = order.customerName
                resp.orderTotalAmount = order.totalAmount

        # Typing feedback
        my_type = SenderType.BAKER.value if current_user.role == Role.BAKER.value else SenderType.ADMIN.value
        is_typing, typing_user = _get_typing_status(c.id, exclude_sender_type=my_type)
        resp.is_typing = is_typing
        resp.typing_user = typing_user

        responses.append(resp)

    return responses


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    req: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Admins or Bakers can create direct conversations."""
    bakery_id = req.bakery_id
    if current_user.role == Role.BAKER.value:
        if not current_user.bakery:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No bakery associated with account")
        bakery_id = current_user.bakery.id

    if not bakery_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bakery ID is required")

    bakery = await db.scalar(select(Bakery).where(Bakery.id == bakery_id))
    if not bakery:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bakery not found")

    subject = req.subject.strip() if req.subject else f"Support request - {bakery.name}"

    conv = Conversation(
        bakery_id=bakery.id,
        subject=subject,
    )
    db.add(conv)
    await db.flush()

    if req.message and req.message.strip():
        sender_type = SenderType.ADMIN.value if current_user.role == Role.SUPER_ADMIN.value else SenderType.BAKER.value
        sender_name = "Platform Support" if current_user.role == Role.SUPER_ADMIN.value else bakery.name
        first_msg = Message(
            conversation_id=conv.id,
            sender_type=sender_type,
            sender_id=current_user.id,
            sender_name=sender_name,
            content=req.message.strip(),
        )
        db.add(first_msg)

    await db.commit()
    await db.refresh(conv)

    # Re-fetch with messages
    conv = await db.scalar(
        select(Conversation)
        .options(selectinload(Conversation.messages), selectinload(Conversation.bakery))
        .where(Conversation.id == conv.id)
    )
    resp = ConversationResponse.model_validate(conv)
    if conv.bakery:
        resp.bakeryName = conv.bakery.name
        resp.bakerySlug = conv.bakery.slug

    return resp


@router.get("/conversations/{conv_id}", response_model=ConversationResponse)
async def get_conversation(
    conv_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Conversation)
        .options(selectinload(Conversation.messages), selectinload(Conversation.bakery))
        .where(Conversation.id == conv_id)
    )

    if current_user.role == Role.BAKER.value:
        if not current_user.bakery:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bakery not found")
        query = query.where(Conversation.bakery_id == current_user.bakery.id)

    conv = await db.scalar(query)
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    # Mark incoming messages as read
    marked = False
    for m in conv.messages:
        if not m.is_read:
            if current_user.role == Role.BAKER.value and m.sender_type != SenderType.BAKER.value:
                m.is_read = True
                marked = True
            elif current_user.role == Role.SUPER_ADMIN.value and m.sender_type != SenderType.ADMIN.value:
                m.is_read = True
                marked = True
    if marked:
        await db.commit()

    resp = ConversationResponse.model_validate(conv)
    if conv.bakery:
        resp.bakeryName = conv.bakery.name
        resp.bakerySlug = conv.bakery.slug

    if conv.order_id:
        order = await db.scalar(select(Order).where(Order.id == conv.order_id))
        if order:
            resp.customerName = order.customerName
            resp.orderTotalAmount = order.totalAmount

    my_type = SenderType.BAKER.value if current_user.role == Role.BAKER.value else SenderType.ADMIN.value
    is_typing, typing_user = _get_typing_status(conv.id, exclude_sender_type=my_type)
    resp.is_typing = is_typing
    resp.typing_user = typing_user

    return resp


@router.post("/conversations/{conv_id}/messages", response_model=MessageResponse)
async def send_message(
    conv_id: str,
    req: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = await db.scalar(
        select(Conversation).options(selectinload(Conversation.bakery)).where(Conversation.id == conv_id)
    )
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    if current_user.role == Role.BAKER.value:
        if not current_user.bakery or conv.bakery_id != current_user.bakery.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    if conv.is_closed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Conversation is closed")

    sender_type = SenderType.ADMIN.value if current_user.role == Role.SUPER_ADMIN.value else SenderType.BAKER.value
    sender_name = "Platform Support" if current_user.role == Role.SUPER_ADMIN.value else (conv.bakery.name if conv.bakery else current_user.name)

    msg = Message(
        conversation_id=conv.id,
        sender_type=sender_type,
        sender_id=current_user.id,
        sender_name=sender_name,
        content=req.content.strip(),
    )
    db.add(msg)

    # Update conversation updated_at
    conv.updated_at = datetime.now(timezone.utc)
    _typing_state.pop(conv.id, None)

    await db.commit()
    await db.refresh(msg)

    return msg


@router.patch("/conversations/{conv_id}/close", response_model=ConversationResponse)
async def close_conversation(
    conv_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = await db.scalar(select(Conversation).where(Conversation.id == conv_id))
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
        
    if current_user.role == Role.BAKER.value and conv.bakery_id != current_user.bakery.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        
    conv.is_closed = True
    await db.commit()
    await db.refresh(conv)
    conv.messages = []

    return conv


# ──────────────────────────────────────────────── Customer Token Access


@router.get("/customer/{token}", response_model=ConversationResponse)
async def get_customer_conversation(token: str, db: AsyncSession = Depends(get_db)):
    """Anonymous customer access using the token from their order."""
    conv = await db.scalar(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.customer_token == token)
    )
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found or invalid token")

    # Mark incoming messages from baker/admin as read
    marked = False
    for m in conv.messages:
        if not m.is_read and m.sender_type != SenderType.CUSTOMER.value:
            m.is_read = True
            marked = True
    if marked:
        await db.commit()
        
    resp = ConversationResponse.model_validate(conv)
    if conv.order_id:
        order = await db.scalar(select(Order).where(Order.id == conv.order_id))
        if order:
            resp.customerName = order.customerName
            resp.orderTotalAmount = order.totalAmount

    is_typing, typing_user = _get_typing_status(conv.id, exclude_sender_type=SenderType.CUSTOMER.value)
    resp.is_typing = is_typing
    resp.typing_user = typing_user
            
    return resp



@router.post("/customer/conversations", response_model=ConversationResponse)
@router.post("/public/conversations", response_model=ConversationResponse)
async def create_customer_conversation(
    req: CustomerConversationCreate,
    db: AsyncSession = Depends(get_db),
):
    """Anonymous customer starts a conversation."""
    bakery = await db.scalar(select(Bakery).where(Bakery.id == req.bakery_id))
    if not bakery:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bakery not found")
        
    import secrets
    customer_token = secrets.token_urlsafe(32)
    
    conv = Conversation(
        bakery_id=bakery.id,
        customer_token=customer_token,
        subject=req.subject or "Customer Inquiry",
    )
    db.add(conv)
    await db.flush()

    init_msg = req.initial_message or req.message
    if init_msg and init_msg.strip():
        sender_name = req.customer_name.strip() if req.customer_name else "Customer"
        msg = Message(
            conversation_id=conv.id,
            sender_type=SenderType.CUSTOMER.value,
            sender_id=None,
            sender_name=sender_name,
            content=init_msg.strip(),
        )
        db.add(msg)

    await db.commit()
    await db.refresh(conv)

    conv = await db.scalar(
        select(Conversation)
        .options(selectinload(Conversation.messages), selectinload(Conversation.bakery))
        .where(Conversation.id == conv.id)
    )
    resp = ConversationResponse.model_validate(conv)
    if conv.bakery:
        resp.bakeryName = conv.bakery.name
        resp.bakerySlug = conv.bakery.slug
    if req.customer_name:
        resp.customerName = req.customer_name

    return resp


@router.post("/customer/{token}/messages", response_model=MessageResponse)
async def customer_send_message(
    token: str,
    req: MessageCreate,
    db: AsyncSession = Depends(get_db),
):
    conv = await db.scalar(select(Conversation).where(Conversation.customer_token == token))
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found or invalid token")
        
    if conv.is_closed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Conversation is closed")
        
    # Get customer name from order if not provided
    sender_name = req.sender_name
    if not sender_name and conv.order_id:
        order = await db.scalar(select(Order).where(Order.id == conv.order_id))
        if order:
            sender_name = order.customerName
            
    if not sender_name:
        sender_name = "Customer"
        
    msg = Message(
        conversation_id=conv.id,
        sender_type=SenderType.CUSTOMER.value,
        sender_id=None,
        sender_name=sender_name,
        content=req.content,
    )
    db.add(msg)
    
    conv.updated_at = __import__('datetime').datetime.now(__import__('datetime').timezone.utc)
    _typing_state.pop(conv.id, None)
    
    await db.commit()
    await db.refresh(msg)
    
    # Real app: create Notification for Baker
    
    return msg


# ──────────────────────────────────────────────── Real-Time Typing Endpoints


@router.post("/conversations/{conv_id}/typing", response_model=TypingStatusResponse)
async def update_typing_status(
    conv_id: str,
    req: TypingStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Notify that the authenticated baker or admin is typing in a conversation."""
    conv = await db.scalar(select(Conversation).where(Conversation.id == conv_id))
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    sender_type = SenderType.BAKER.value if current_user.role == Role.BAKER.value else SenderType.ADMIN.value
    sender_name = current_user.bakery.name if (current_user.role == Role.BAKER.value and current_user.bakery) else (current_user.name or "Support")

    if req.is_typing:
        _typing_state[conv_id] = {
            "sender_type": sender_type,
            "sender_name": sender_name,
            "expires_at": time.time() + 4.0,
        }
    else:
        _typing_state.pop(conv_id, None)

    return TypingStatusResponse(is_typing=req.is_typing, sender_type=sender_type, sender_name=sender_name)


@router.get("/conversations/{conv_id}/typing", response_model=TypingStatusResponse)
async def get_typing_status(
    conv_id: str,
    current_user: User = Depends(get_current_user),
):
    """Check if the counterparty is typing in a conversation."""
    my_type = SenderType.BAKER.value if current_user.role == Role.BAKER.value else SenderType.ADMIN.value
    is_typing, typing_user = _get_typing_status(conv_id, exclude_sender_type=my_type)
    return TypingStatusResponse(
        is_typing=is_typing,
        sender_type="CUSTOMER" if is_typing and my_type == SenderType.BAKER.value else ("BAKER" if is_typing else None),
        sender_name=typing_user,
    )


@router.post("/customer/{token}/typing", response_model=TypingStatusResponse)
async def customer_update_typing_status(
    token: str,
    req: TypingStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Notify that the anonymous customer is typing."""
    conv = await db.scalar(select(Conversation).where(Conversation.customer_token == token))
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    if req.is_typing:
        _typing_state[conv.id] = {
            "sender_type": SenderType.CUSTOMER.value,
            "sender_name": "Customer",
            "expires_at": time.time() + 4.0,
        }
    else:
        _typing_state.pop(conv.id, None)

    return TypingStatusResponse(is_typing=req.is_typing, sender_type=SenderType.CUSTOMER.value, sender_name="Customer")


@router.get("/customer/{token}/typing", response_model=TypingStatusResponse)
async def customer_get_typing_status(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Customer checks if the baker is typing."""
    conv = await db.scalar(select(Conversation).where(Conversation.customer_token == token))
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    is_typing, typing_user = _get_typing_status(conv.id, exclude_sender_type=SenderType.CUSTOMER.value)
    return TypingStatusResponse(
        is_typing=is_typing,
        sender_type=SenderType.BAKER.value if is_typing else None,
        sender_name=typing_user or "Baker",
    )
