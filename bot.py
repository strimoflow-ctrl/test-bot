"""
Lightweight Test Telegram Bot for Railway Deployment.
Connects to an external API endpoint via environment variables.
"""

import os
import re
import time
import html
import requests
import telebot
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
API_URL = os.environ.get("API_URL", "").strip()

if not BOT_TOKEN:
    print("[WARN] BOT_TOKEN is not set! Set BOT_TOKEN in environment or .env file.")

bot = telebot.TeleBot(BOT_TOKEN if BOT_TOKEN else "DUMMY_TOKEN")


def clean_phone(val):
    if not val:
        return ""
    # Strip all non-digit characters (spaces, dashes, plus, brackets, etc.)
    digits = re.sub(r"\D", "", str(val).strip())
    if not digits:
        return ""

    # If starts with 91 and has 12 digits (e.g. +91 9876543210 -> 919876543210)
    if len(digits) == 12 and digits.startswith("91"):
        return digits[2:]
    
    # If starts with 0 and has 11 digits (e.g. 09876543210)
    if len(digits) == 11 and digits.startswith("0"):
        return digits[1:]
        
    # Standard 10 digits
    if len(digits) == 10:
        return digits

    # If longer and starts with 91, take the 10 digits after 91
    if len(digits) > 10 and digits.startswith("91"):
        return digits[2:12]

    # Fallback to last 10 digits if 10 or more digits
    if len(digits) >= 10:
        return digits[-10:]

    return digits


def find_records(data):
    """Recursively search for list of records in nested response."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # Look for result list
        for key in ["result", "data", "records"]:
            if key in data:
                sub = data[key]
                if isinstance(sub, list):
                    return sub
                elif isinstance(sub, dict):
                    res = find_records(sub)
                    if res:
                        return res
    return []


@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    text = (
        "🤖 <b>Test Lookup Bot is Live!</b>\n\n"
        "Send any mobile number in any format:\n"
        "• <code>9876543210</code>\n"
        "• <code>+91 98765 43210</code>\n"
        "• <code>91-9876543210</code>\n"
        "• <code>09876543210</code>\n\n"
        "💡 <b>Example:</b> <code>6392551618</code>"
    )
    bot.reply_to(message, text, parse_mode="HTML")


@bot.message_handler(func=lambda msg: True)
def handle_number(message):
    raw = message.text.strip()
    phone = clean_phone(raw)

    if not phone or len(phone) < 10:
        bot.reply_to(
            message, 
            "⚠️ <b>Invalid Number!</b>\nPlease enter a valid 10-digit mobile number.\n<i>Examples:</i> <code>9876543210</code> or <code>+91 9876543210</code>",
            parse_mode="HTML"
        )
        return

    target_api = API_URL
    if not target_api:
        bot.reply_to(message, "⚠️ API_URL environment variable is not configured on the server.")
        return

    # Check query format
    lookup_url = target_api if target_api.endswith("=") else f"{target_api}?number="
    full_url = f"{lookup_url}{phone}"

    t0 = time.time()
    try:
        res = requests.get(full_url, timeout=12)
        elapsed = round(time.time() - t0, 2)

        if res.status_code != 200:
            bot.reply_to(
                message,
                f"❌ <b>API Error:</b> HTTP {res.status_code}\n<i>Response Time: {elapsed}s</i>",
                parse_mode="HTML"
            )
            return

        data = res.json()
        records = find_records(data)

        if not records:
            bot.reply_to(
                message,
                f"🔍 <b>No Record Found!</b>\nNumber: <code>{html.escape(phone)}</code>\n<i>Response Time: {elapsed}s</i>",
                parse_mode="HTML"
            )
            return

        response_text = f"📱 <b>NUMBER INFO</b>\n"
        response_text += f"Query: <code>{html.escape(phone)}</code>\n"
        response_text += f"Records: <b>{len(records)}</b>\n"
        response_text += "──────────────────────────\n"

        for idx, item in enumerate(records, 1):
            if not isinstance(item, dict):
                response_text += f"\n{html.escape(str(item))}\n"
                continue

            response_text += f"\n📋 <b>RECORD {idx}/{len(records)}</b>\n"
            
            # Map standard fields nicely
            name = item.get("name") or item.get("customer_name") or item.get("person_name")
            fname = item.get("fname") or item.get("father") or item.get("father_name")
            num = item.get("num") or item.get("mobile") or item.get("phone") or phone
            alt = item.get("alt") or item.get("alt_num") or item.get("alternate")
            circle = item.get("circle") or item.get("telecom_circle")
            addr = item.get("address")
            id_val = item.get("aadhar") or item.get("id") or item.get("id_number")

            if num:
                response_text += f"📱 <b>Number:</b> <code>{html.escape(str(num))}</code>\n"
            if name:
                response_text += f"👤 <b>Name:</b> {html.escape(str(name))}\n"
            if fname:
                response_text += f"👨‍👦 <b>Father:</b> {html.escape(str(fname))}\n"
            if alt:
                response_text += f"📞 <b>Alt Num:</b> <code>{html.escape(str(alt))}</code>\n"
            if circle:
                response_text += f"🌐 <b>Circle:</b> {html.escape(str(circle))}\n"
            if id_val:
                response_text += f"🪪 <b>ID:</b> <code>{html.escape(str(id_val))}</code>\n"
            if addr:
                response_text += f"🏠 <b>Address:</b> {html.escape(str(addr))}\n"

            # Any other remaining fields
            handled_keys = {"name", "customer_name", "person_name", "fname", "father", "father_name", 
                            "num", "mobile", "phone", "alt", "alt_num", "alternate", "circle", 
                            "telecom_circle", "address", "aadhar", "id", "id_number"}
            for k, v in item.items():
                if k not in handled_keys and v:
                    clean_k = html.escape(k.replace("_", " ").title())
                    clean_v = html.escape(str(v))
                    response_text += f"• <b>{clean_k}:</b> {clean_v}\n"

        response_text += f"\n⚡ <i>Response Time: {elapsed}s</i>"

        # If message is within Telegram 4096 char limit
        if len(response_text) <= 4000:
            bot.reply_to(message, response_text, parse_mode="HTML")
        else:
            # Chunk long messages
            for chunk in [response_text[i:i+3800] for i in range(0, len(response_text), 3800)]:
                bot.reply_to(message, chunk, parse_mode="HTML")

    except requests.exceptions.Timeout:
        bot.reply_to(message, "⏱️ <b>Timeout Error:</b> The API took more than 12 seconds to respond.", parse_mode="HTML")
    except Exception as e:
        # Fallback safe error message without breaking parse_mode
        bot.reply_to(message, f"⚠️ <b>Error:</b> {html.escape(str(e))}", parse_mode="HTML")


if __name__ == "__main__":
    if not BOT_TOKEN:
        print("[ERROR] BOT_TOKEN is missing. Set it in .env or environment variables.")
    else:
        print("🤖 Test Bot is starting polling...")
        bot.infinity_polling(timeout=20, long_polling_timeout=15)
