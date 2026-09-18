"""
Lightweight Test Telegram Bot for Railway Deployment.
Connects to an external API endpoint via environment variables.
Size: < 5 KB (Instant upload to GitHub / Railway).
"""

import os
import re
import time
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
    digits = re.sub(r"\D", "", str(val).strip())
    if len(digits) >= 10:
        return digits[-10:]
    return digits


@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    text = (
        "🤖 *Test Lookup Bot is Live!*\n\n"
        "Send any *10-digit mobile number* to test the API lookup.\n\n"
        "💡 *Example:* `6392551618`"
    )
    bot.reply_to(message, text, parse_mode="Markdown")


@bot.message_handler(func=lambda msg: True)
def handle_number(message):
    raw = message.text.strip()
    phone = clean_phone(raw)

    if not phone or len(phone) < 10:
        bot.reply_to(message, "⚠️ Please send a valid 10-digit phone number.")
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
        res = requests.get(full_url, timeout=10)
        elapsed = round(time.time() - t0, 2)

        if res.status_code != 200:
            bot.reply_to(
                message,
                f"❌ *API Error:* HTTP {res.status_code}\n\n_Response Time: {elapsed}s_",
                parse_mode="Markdown"
            )
            return

        data = res.json()

        # Format whatever data comes from the API dynamically
        response_text = f"📱 *LOOKUP RESULT FOR:* `{phone}`\n"
        response_text += "──────────────────────────\n"

        if isinstance(data, list):
            if not data:
                response_text += "❌ No records found in response list.\n"
            else:
                for idx, item in enumerate(data, 1):
                    response_text += f"\n📋 *Record {idx}/{len(data)}:*\n"
                    if isinstance(item, dict):
                        for k, v in item.items():
                            if v:
                                response_text += f"• *{k.replace('_', ' ').title()}:* {v}\n"
                    else:
                        response_text += f"{item}\n"
        elif isinstance(data, dict):
            # Check for error or empty
            if data.get("error") or data.get("message"):
                response_text += f"ℹ️ *Message:* {data.get('error') or data.get('message')}\n"
            
            # Format dictionary keys
            for k, v in data.items():
                if v and not isinstance(v, (dict, list)):
                    response_text += f"• *{k.replace('_', ' ').title()}:* {v}\n"
                elif isinstance(v, list) and v:
                    response_text += f"\n📂 *{k.title()}:*\n"
                    for sub in v:
                        if isinstance(sub, dict):
                            for sk, sv in sub.items():
                                if sv:
                                    response_text += f"   - *{sk.title()}:* {sv}\n"
        else:
            response_text += str(data)[:500]

        response_text += f"\n⚡ _Response Time: {elapsed}s_"
        bot.reply_to(message, response_text, parse_mode="Markdown")

    except requests.exceptions.Timeout:
        bot.reply_to(message, "⏱️ *Timeout Error:* The API took more than 10 seconds to respond.")
    except Exception as e:
        bot.reply_to(message, f"⚠️ *Error:* {str(e)}")


if __name__ == "__main__":
    if not BOT_TOKEN:
        print("[ERROR] BOT_TOKEN is missing. Set it in .env or environment variables.")
    else:
        print("🤖 Test Bot is starting polling...")
        bot.infinity_polling(timeout=20, long_polling_timeout=15)
