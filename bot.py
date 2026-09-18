"""
Lightweight Clean Lookup Telegram Bot for Railway Deployment.
Cleans raw JSON, removes spam/tags/watermarks, and formats beautifully without any parse errors.
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
API_URL = os.environ.get("API_URL", "https://nmdllpezcocquamhgpmb.supabase.co/functions/v1/lookup?number=").strip()

if not BOT_TOKEN:
    print("[WARN] BOT_TOKEN is not set! Set BOT_TOKEN in environment or .env file.")

bot = telebot.TeleBot(BOT_TOKEN if BOT_TOKEN else "DUMMY_TOKEN")


def clean_phone(val):
    if not val:
        return ""
    # Strip everything except digits
    digits = re.sub(r"\D", "", str(val).strip())
    if not digits:
        return ""

    # 12 digits starting with 91 (e.g. +91 6392551618 -> 6392551618)
    if len(digits) == 12 and digits.startswith("91"):
        return digits[2:]

    # 11 digits starting with 0 (e.g. 06392551618 -> 6392551618)
    if len(digits) == 11 and digits.startswith("0"):
        return digits[1:]

    # 10 digits standard
    if len(digits) == 10:
        return digits

    # More than 10 digits starting with 91
    if len(digits) > 10 and digits.startswith("91"):
        return digits[2:12]

    # Fallback to last 10 digits
    if len(digits) >= 10:
        return digits[-10:]

    return digits


def extract_clean_records(data):
    """
    Unwraps nested JSON response, filters out spam/watermark tags,
    cleans up formatting and removes duplicate records.
    """
    cur = data
    # Traverse through nested dicts
    while isinstance(cur, dict):
        if "result" in cur:
            cur = cur["result"]
        elif "data" in cur:
            cur = cur["data"]
        elif "records" in cur:
            cur = cur["records"]
        else:
            break

    raw_records = cur if isinstance(cur, list) else []
    cleaned = []
    seen = set()

    for item in raw_records:
        if not isinstance(item, dict):
            continue

        # Extract primary fields
        num = item.get("num") or item.get("mobile") or item.get("phone") or ""
        name = item.get("name") or item.get("customer_name") or ""
        fname = item.get("fname") or item.get("father") or item.get("father_name") or ""
        alt = item.get("alt") or item.get("alt_num") or ""
        circle = item.get("circle") or item.get("telecom_circle") or ""
        id_val = item.get("aadhar") or item.get("id") or ""
        addr = item.get("address") or ""

        # Deduplicate identical records
        uid = f"{num}-{name}-{id_val}"
        if uid in seen and uid != "--":
            continue
        seen.add(uid)

        # Clean address: replace '!' with ', ' and normalize spaces
        if addr:
            addr = re.sub(r"[!]+", ", ", addr)
            addr = re.sub(r"\s+", " ", addr).strip(", ")

        cleaned.append({
            "num": num,
            "name": name,
            "fname": fname,
            "alt": alt,
            "circle": circle,
            "id": id_val,
            "address": addr
        })

    return cleaned


@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    text = (
        "🤖 <b>Number Lookup Bot is Live!</b>\n\n"
        "Send any mobile number in any format:\n"
        "• <code>6392551618</code>\n"
        "• <code>+91 63925 51618</code>\n"
        "• <code>91-6392551618</code>\n"
        "• <code>06392551618</code>\n\n"
        "💡 <i>Bot automatically removes spaces, +91, and cleans input!</i>"
    )
    bot.reply_to(message, text, parse_mode="HTML")


@bot.message_handler(func=lambda msg: True)
def handle_number(message):
    raw = message.text.strip()
    phone = clean_phone(raw)

    if not phone or len(phone) < 10:
        bot.reply_to(
            message,
            "⚠️ <b>Invalid Number!</b>\nPlease enter a valid 10-digit mobile number.\n<i>Example:</i> <code>6392551618</code>",
            parse_mode="HTML"
        )
        return

    target_api = API_URL
    if not target_api:
        bot.reply_to(message, "⚠️ API_URL environment variable is not configured.", parse_mode="HTML")
        return

    lookup_url = target_api if target_api.endswith("=") else f"{target_api}?number="
    full_url = f"{lookup_url}{phone}"

    t0 = time.time()
    try:
        res = requests.get(full_url, timeout=15)
        elapsed = round(time.time() - t0, 2)

        if res.status_code != 200:
            bot.reply_to(
                message,
                f"❌ <b>API Error:</b> HTTP {res.status_code}\n<i>Response Time: {elapsed}s</i>",
                parse_mode="HTML"
            )
            return

        data = res.json()
        records = extract_clean_records(data)

        if not records:
            bot.reply_to(
                message,
                f"🔍 <b>No Record Found!</b>\nQuery: <code>{html.escape(phone)}</code>\n<i>Response Time: {elapsed}s</i>",
                parse_mode="HTML"
            )
            return

        response_text = "📱 <b>NUMBER INFO</b>\n"
        response_text += f"Query: <code>{html.escape(phone)}</code>\n"
        response_text += f"Records: <b>{len(records)}</b>\n"
        response_text += "──────────────────────────\n"

        for idx, item in enumerate(records, 1):
            if len(records) > 1:
                response_text += f"\n📋 <b>RECORD {idx}/{len(records)}</b>\n"

            if item["num"]:
                response_text += f"📱 <b>Number:</b> <code>{html.escape(str(item['num']))}</code>\n"
            if item["name"]:
                response_text += f"👤 <b>Name:</b> {html.escape(str(item['name']))}\n"
            if item["fname"]:
                response_text += f"👨‍👦 <b>Father:</b> {html.escape(str(item['fname']))}\n"
            if item["alt"]:
                response_text += f"📞 <b>Alt Num:</b> <code>{html.escape(str(item['alt']))}</code>\n"
            if item["circle"]:
                response_text += f"🌐 <b>Circle:</b> {html.escape(str(item['circle']))}\n"
            if item["id"]:
                response_text += f"🪪 <b>ID:</b> <code>{html.escape(str(item['id']))}</code>\n"
            if item["address"]:
                response_text += f"🏠 <b>Address:</b> {html.escape(str(item['address']))}\n"

        response_text += "──────────────────────────\n"
        response_text += f"⚡ <i>Response Time: {elapsed}s</i>"

        # Telegram message length safety
        if len(response_text) <= 4000:
            bot.reply_to(message, response_text, parse_mode="HTML")
        else:
            for chunk in [response_text[i:i+3800] for i in range(0, len(response_text), 3800)]:
                bot.reply_to(message, chunk, parse_mode="HTML")

    except requests.exceptions.Timeout:
        bot.reply_to(message, "⏱️ <b>Timeout:</b> API took too long to respond. Please try again.", parse_mode="HTML")
    except Exception as e:
        # Never break with parse_mode on unexpected errors
        clean_err = html.escape(str(e))
        bot.reply_to(message, f"⚠️ <b>Error:</b> {clean_err}", parse_mode="HTML")


if __name__ == "__main__":
    if not BOT_TOKEN:
        print("[ERROR] BOT_TOKEN is missing. Set it in .env or environment variables.")
    else:
        print("🤖 Clean Lookup Bot is starting polling...")
        bot.infinity_polling(timeout=20, long_polling_timeout=15)
