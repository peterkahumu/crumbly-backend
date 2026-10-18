from app.config import get_settings


def format_price(value: float | int) -> str:
    return f"{get_settings().currency} {value:,.0f}"
