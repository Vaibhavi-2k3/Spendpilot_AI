
import re
from decimal import Decimal, InvalidOperation


CURRENCY_SYMBOLS = {
    "USD": "$",
    "INR": "₹",
}


def parse_product_price(
    price_text: str,
    currency: str,
) -> Decimal | None:
    symbol = CURRENCY_SYMBOLS.get(currency)

    if symbol is None:
        raise ValueError(
            f"Unsupported price currency: {currency}"
        )

    if not isinstance(price_text, str):
        return None

    text = price_text.strip()

    # Reject explicit currency markers for another market.
    if currency == "USD" and (
        "₹" in text or "INR" in text.upper()
    ):
        return None

    if currency == "INR" and (
        "$" in text or "USD" in text.upper()
    ):
        return None

    # INR listings may use either 1,234,567 or Indian grouping: 12,34,567.
    grouped_amount = r"\d{1,3}(?:,\d{3})+"
    if currency == "INR":
        grouped_amount += r"|\d{1,2}(?:,\d{2})+,\d{3}"

    # Accept only a single, clearly formatted amount.
    pattern = (
        rf"^(?:{re.escape(symbol)}\s*)?"
        rf"(?:\d+|{grouped_amount})"
        rf"(?:\.\d{{1,2}})?$"
    )

    if not re.fullmatch(pattern, text):
        return None

    try:
        amount = Decimal(
            text.replace(symbol, "")
            .replace(",", "")
            .strip()
        )
    except InvalidOperation:
        return None

    if not amount.is_finite() or amount < 0:
        return None

    return amount
