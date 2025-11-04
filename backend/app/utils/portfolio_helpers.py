"""Portfolio helper functions for currency conversion and formatting"""
from ..services.currency_service import currency_service
try:
    from utils.logger import get_logger
except Exception:  # pragma: no cover
    from ..utils.logger import get_logger

logger = get_logger("backend.app.utils.portfolio_helpers")


def format_total_investment_text(amount: float, currency: str) -> str:
    """Format total investment text with proper currency symbol"""
    if not amount or amount == 0:
        return f"0 {currency}"

    # Format number with commas for thousands
    formatted_amount = f"{amount:,.0f}" if amount >= 1 else f"{amount:.8f}".rstrip('0').rstrip('.')

    # Add currency symbol
    currency_symbols = {
        "USD": "$",
        "EUR": "€",
        "CZK": "Kč",
        "GBP": "£",
        "JPY": "¥"
    }

    symbol = currency_symbols.get(currency, currency)
    return f"{symbol}{formatted_amount}" if symbol in ["$", "€", "£", "¥"] else f"{formatted_amount} {symbol}"


def convert_portfolio_item(item: dict, target_currency: str) -> dict:
    """Convert a portfolio item to target currency using USD-based calculations"""
    if item["base_currency"] == target_currency:
        # Ensure total_investment_text is properly formatted even without conversion
        if not item.get("total_investment_text") or not any(symbol in item.get("total_investment_text", "") for symbol in ["$", "€", "Kč", "£", "¥"]):
            total_investment = (item["amount"] * item["price_buy"]) + item.get("commission", 0)
            item["total_investment_text"] = format_total_investment_text(total_investment, target_currency)
        return item

    try:
        # Use USD values for calculations if available, otherwise convert from display currency
        if item.get("price_buy_usd") is not None:
            # Use stored USD values for accurate calculations
            price_buy_usd = item["price_buy_usd"]
            commission_usd = item.get("commission_usd", 0)
            current_value_usd = item.get("current_value_usd", 0)
            pnl_usd = item.get("pnl_usd", 0)
        else:
            # Fallback: convert from display currency to USD
            price_buy_usd = currency_service.convert_amount(item["price_buy"], item["base_currency"], "USD")
            commission_usd = currency_service.convert_amount(item.get("commission", 0), item["base_currency"], "USD")
            current_value_usd = currency_service.convert_amount(item.get("current_value", 0), item["base_currency"], "USD") if item.get("current_value") else 0
            pnl_usd = currency_service.convert_amount(item.get("pnl", 0), item["base_currency"], "USD") if item.get("pnl") else 0

        # Convert USD values to target currency for display
        converted_price_buy = currency_service.convert_amount(price_buy_usd, "USD", target_currency)
        converted_commission = currency_service.convert_amount(commission_usd, "USD", target_currency)
        converted_current_value = currency_service.convert_amount(current_value_usd, "USD", target_currency) if current_value_usd else None
        converted_pnl = currency_service.convert_amount(pnl_usd, "USD", target_currency) if pnl_usd else None

        # Convert current price for display
        converted_current_price = None
        if item.get("current_price_usd") is not None:
            converted_current_price = currency_service.convert_amount(item["current_price_usd"], "USD", target_currency)
        elif item.get("current_price"):
            converted_current_price = currency_service.convert_amount(item["current_price"], item["base_currency"], target_currency)

        # Calculate total investment in target currency
        total_investment = (item["amount"] * converted_price_buy) + converted_commission

        # Calculate P&L percentage using USD values for accuracy
        pnl_percent = item.get("pnl_percent_usd") if item.get("pnl_percent_usd") is not None else item.get("pnl_percent", 0)

        return {
            **item,
            "base_currency": target_currency,
            "price_buy": round(converted_price_buy, 8),
            "current_price": round(converted_current_price, 8) if converted_current_price else None,
            "current_value": round(converted_current_value, 8) if converted_current_value else None,
            "pnl": round(converted_pnl, 8) if converted_pnl else None,
            "pnl_percent": round(pnl_percent, 8),
            "commission": round(converted_commission, 8),
            "total_investment_text": format_total_investment_text(total_investment, target_currency)
        }
    except Exception as e:
        logger.error(f"Currency conversion error: {e}")
        return item
