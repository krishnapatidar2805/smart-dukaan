"""
WhatsApp notification helpers (via Twilio).

This is OPTIONAL. If Twilio credentials are not set in your .env file,
these functions simply skip sending and return False - the rest of the
app works normally without them.

To enable real WhatsApp messages:
1. Create a free account at https://www.twilio.com
2. Activate the WhatsApp Sandbox (Messaging -> Try it out -> WhatsApp)
3. Copy your Account SID, Auth Token, and Sandbox WhatsApp number
4. Put them in your .env file (see .env.example)
5. pip install twilio
"""
import os


def _twilio_client():
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    if not sid or not token:
        return None
    try:
        from twilio.rest import Client
    except ImportError:
        return None
    return Client(sid, token)


def send_whatsapp_message(to_phone: str, message: str) -> bool:
    """Send a WhatsApp message. Returns True if sent, False if skipped/failed."""
    client = _twilio_client()
    from_whatsapp = os.environ.get("TWILIO_WHATSAPP_FROM")  # e.g. 'whatsapp:+14155238886'
    if not client or not from_whatsapp or not to_phone:
        return False
    try:
        clean_phone = to_phone if to_phone.startswith("+") else f"+91{to_phone.strip()}"
        client.messages.create(
            from_=from_whatsapp,
            to=f"whatsapp:{clean_phone}",
            body=message,
        )
        return True
    except Exception:
        return False


def build_bill_message(bill) -> str:
    shop_name = bill.shop.name
    lines = [f"Namaste! Your bill from *{shop_name}*", ""]
    for item in bill.items.all():
        lines.append(f"- {item.product_name_snapshot} x{item.quantity} = Rs.{item.line_total}")
    lines.append("")
    lines.append(f"Total: Rs.{bill.total_amount}")
    lines.append(f"Payment: {bill.get_payment_mode_display()}")
    lines.append("")
    lines.append("Thank you for shopping with us!")
    return "\n".join(lines)


def build_udhaar_reminder_message(customer) -> str:
    return (
        f"Namaste {customer.name} ji,\n\n"
        f"Aapka udhaar (credit) balance Rs.{customer.total_due} baaki hai.\n"
        f"Kripya jaldi clear karein. Dhanyawad!"
    )
