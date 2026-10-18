import urllib.parse
from app.utils.currency import format_price


def build_whatsapp_order_link(bakery, order, conversation_token: str | None = None) -> str:
    """Builds the WhatsApp wa.me link for an order, porting the logic from frontend."""
    phone = bakery.whatsappNumber
    # Strip any non-digit chars and ensure it starts with country code (assuming Kenya 254 if starts with 0)
    clean_phone = "".join(filter(str.isdigit, phone))
    if clean_phone.startswith("0"):
        clean_phone = f"254{clean_phone[1:]}"

    lines = [
        f"Hello {bakery.name}!",
        f"I'm {order.customerName} (Phone: {order.customerPhone}).",
        "",
        "I'd like to place an order for:",
    ]

    for item in order.items:
        lines.append(f"• {item['qty']}x {item['name']} - {format_price(item['price'])}")

    lines.extend([
        "",
        f"Total: {format_price(order.totalAmount)}",
        "",
        f"Order reference: {order.id}",
    ])

    if conversation_token:
        # Assuming frontend will be deployed somewhere, but we'll use NEXT_PUBLIC_FRONTEND_URL later.
        # For now, let's just say "Use this link to chat with me: /messages/{token}"
        # Since backend doesn't know frontend URL natively, we'll just include the token and instructions
        lines.extend([
            "",
            f"You can also chat with me directly in your storefront here:",
            f"(Ask me for the link! Token: {conversation_token})"
        ])

    text = "\n".join(lines)
    encoded_text = urllib.parse.quote(text)
    
    return f"https://wa.me/{clean_phone}?text={encoded_text}"
