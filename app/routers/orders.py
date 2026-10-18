import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import Bakery, Conversation, Order, OrderStatus, Role, User
from app.schemas.order import OrderCreate, OrderResponse, OrderUpdate

router = APIRouter(prefix="/orders", tags=["orders"])



@router.get("", response_model=list[OrderResponse])
async def list_orders(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role == Role.SUPER_ADMIN.value:
        # Admin sees all orders
        result = await db.execute(
            select(Order).options(selectinload(Order.bakery)).order_by(Order.createdAt.desc())
        )
    else:
        # Baker sees their own orders
        if not current_user.bakery:
            return []
        result = await db.execute(
            select(Order)
            .options(selectinload(Order.bakery))
            .where(Order.bakeryId == current_user.bakery.id)
            .order_by(Order.createdAt.desc())
        )
        
    orders = result.scalars().all()
    
    # We don't expose conversationToken in the list response to protect it, 
    # except maybe for the baker/admin? Actually they don't need it.
    return orders


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    req: OrderCreate,
    db: AsyncSession = Depends(get_db),
):
    bakery = await db.scalar(select(Bakery).where(Bakery.id == req.bakeryId))
    if not bakery or bakery.isDeleted or bakery.status != "APPROVED":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bakery not found or unavailable")

    total_amount = sum(item.price * item.qty for item in req.items)
    
    order = Order(
        bakeryId=bakery.id,
        customerName=req.customerName.strip(),
        customerPhone=req.customerPhone.strip(),
        items=[item.model_dump() for item in req.items],
        totalAmount=total_amount,
        status=OrderStatus.PENDING.value,
        channel="WHATSAPP",
    )
    db.add(order)
    await db.flush()  # to get order.id

    # Create a conversation thread for this order so the customer can message the baker
    # Generate a secure random token for the customer
    customer_token = secrets.token_urlsafe(32)
    
    conv = Conversation(
        order_id=order.id,
        bakery_id=bakery.id,
        customer_token=customer_token,
        subject=f"Order #{order.id[-6:].upper()} from {order.customerName}",
    )
    db.add(conv)
    
    await db.commit()
    await db.refresh(order)
    
    # Let's attach the conversation token to the response so the frontend can store it
    # and use it for the WhatsApp link
    
    order.bakery = bakery
    response_data = OrderResponse.model_validate(order)
    response_data.conversationToken = customer_token
    
    # You would also probably generate the whatsapp link here or let frontend do it
    # with the token included
    
    return response_data


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Order).options(selectinload(Order.bakery)).where(Order.id == order_id)
    if current_user.role == Role.BAKER.value:
        if not current_user.bakery:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bakery not found")
        query = query.where(Order.bakeryId == current_user.bakery.id)

    order = await db.scalar(query)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    return order


@router.patch("/{order_id}", response_model=OrderResponse)
async def update_order(
    order_id: str,
    req: OrderUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Order).options(selectinload(Order.bakery)).where(Order.id == order_id)
    if current_user.role == Role.BAKER.value:
        if not current_user.bakery:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bakery not found")
        query = query.where(Order.bakeryId == current_user.bakery.id)

    order = await db.scalar(query)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if req.status is not None:
        order.status = req.status
    if req.customerName is not None:
        order.customerName = req.customerName.strip()
    if req.customerPhone is not None:
        order.customerPhone = req.customerPhone.strip()
    if req.totalAmount is not None:
        order.totalAmount = req.totalAmount
    if req.mpesaReceiptNumber is not None:
        order.mpesaReceiptNumber = req.mpesaReceiptNumber.strip()

    await db.commit()
    await db.refresh(order)

    return order
