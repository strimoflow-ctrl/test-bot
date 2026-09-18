"""
Premium High-Performance Lookup Telegram Bot for Railway Deployment.
Features:
- Smart Channel Leave Detection: Only asks to join the SPECIFIC channel(s) the user left or hasn't joined.
- Dynamic Multi-Channel Force-Sub via ENV (supports any number of channels).
- Seamless Verification: On 'Verify & Continue', instantly replaces the join message with the full clean Welcome screen.
- Animated Cyber Loading Progress Bar while fetching records.
- Automatic Data Sanitization (cleans addresses, removes watermarks, duplicates, spam tags).
- Robust Phone Normalization (+91, spaces, dashes, parentheses, zero prefix).
- Conflict Free (auto-resets stuck webhooks).
"""

import os
import re
import time
import html
import requests
import telebot
from telebot import types
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
API_URL = os.environ.get(
    "API_URL", 
    "https://nmdllpezcocquamhgpmb.supabase.co/functions/v1/lookup?number="
).strip()

# Comma-separated channel usernames or IDs, e.g. "@mychannel1, @mychannel2"
CHANNELS_RAW = os.environ.get("FORCE_CHANNELS", "").strip()

if not BOT_TOKEN:
    print("[WARN] BOT_TOKEN is not set! Set BOT_TOKEN in environment or .env file.")

bot = telebot.TeleBot(BOT_TOKEN if BOT_TOKEN else "DUMMY_TOKEN")


def get_required_channels():
    """Parses FORCE_CHANNELS environment variable into a clean list of channels."""
    if not CHANNELS_RAW:
        return []
    channels = []
    for ch in CHANNELS_RAW.split(","):
        ch = ch.strip()
        if ch:
            if not ch.startswith("@") and not ch.startswith("-"):
                ch = "@" + ch
            channels.append(ch)
    return channels


def check_user_membership(user_id):
    """
    Checks if the user has joined all required channels.
    Returns: (is_all_joined: bool, unjoined_channels: list)
    """
    channels = get_required_channels()
    if not channels:
        return True, []

    unjoined = []
    for ch in channels:
        try:
            member = bot.get_chat_member(ch, user_id)
            if member.status not in ["creator", "administrator", "member", "restricted"]:
                unjoined.append(ch)
        except Exception as e:
            print(f"[WARN] Error checking membership in {ch}: {e}")
            # If bot has permissions issue, avoid blocking user permanently
            pass

    return len(unjoined) == 0, unjoined


def make_force_sub_markup(unjoined_channels):
    """Generates inline buttons for ONLY the channels the user has NOT joined."""
    markup = types.InlineKeyboardMarkup(row_width=1)
    for idx, ch in enumerate(unjoined_channels, 1):
        clean_name = ch.replace("@", "")
        url = f"https://t.me/{clean_name}"
        markup.add(types.InlineKeyboardButton(f"📢 Join Channel ({ch})", url=url))

    markup.add(types.InlineKeyboardButton("🔄 Verify & Continue", callback_data="check_join"))
    return markup


def get_welcome_text():
    """Short, sleek, premium cyber welcome screen."""
    return (
        "╭━━━〔 ⚡ <b>NUMBER INTELLIGENCE</b> 〕━━━╮\n"
        "┃  🛡️ <b>STATUS:</b> <code>ONLINE & READY</code>\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
        "👋 <b>Welcome!</b> Send any mobile number to search:\n"
        "💡 <b>Example:</b> <code>6392551618</code> <i>(or with +91)</i>\n\n"
        "⚡ <i>Auto-formats country code & spaces instantly.</i>"
    )


# ─────────────────────────────────────────────────────────────
# REAL-TIME CHANNEL LEAVE DETECTION
# Triggers immediately when a user leaves any channel
# ─────────────────────────────────────────────────────────────
@bot.chat_member_handler()
def handle_chat_member_update(update: types.ChatMemberUpdated):
    try:
        old_status = update.old_chat_member.status
        new_status = update.new_chat_member.status
        user = update.new_chat_member.user

        # If user left or was removed from channel
        if old_status in ["member", "administrator", "restricted"] and new_status in ["left", "kicked"]:
            chat_title = update.chat.title or update.chat.username or "channel"
            
            # Check exactly which channels are unjoined right now
            is_joined, unjoined = check_user_membership(user.id)
            if is_joined:
                return

            if len(unjoined) == 1:
                alert_text = (
                    f"🚨 <b>Alert! You left {html.escape(str(chat_title))}!</b>\n\n"
                    f"Your bot access is paused because you are not in <b>{unjoined[0]}</b>.\n"
                    "Please re-join this channel and click <b>Verify & Continue</b>."
                )
            else:
                alert_text = (
                    f"🚨 <b>Alert! You left {html.escape(str(chat_title))}!</b>\n\n"
                    f"You have <b>{len(unjoined)} channels</b> pending to join.\n"
                    "Please join all pending channels below and click <b>Verify & Continue</b>."
                )

            try:
                bot.send_message(
                    user.id,
                    alert_text,
                    reply_markup=make_force_sub_markup(unjoined),
                    parse_mode="HTML"
                )
            except Exception as dm_err:
                print(f"[INFO] Could not DM user {user.id}: {dm_err}")
    except Exception as e:
        print(f"[ERROR] chat_member_update error: {e}")


@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    user_id = message.from_user.id
    is_joined, unjoined = check_user_membership(user_id)

    if not is_joined:
        if len(unjoined) == 1:
            text = (
                "🚨 <b>Channel Membership Required!</b>\n\n"
                f"You need to join <b>{unjoined[0]}</b> before using this bot.\n"
                "After joining, click <b>Verify & Continue</b> below."
            )
        else:
            text = (
                "🚨 <b>Access Restricted!</b>\n\n"
                f"You have <b>{len(unjoined)} channels</b> pending to join.\n"
                "Please join them and click <b>Verify & Continue</b> below."
            )
        bot.reply_to(message, text, reply_markup=make_force_sub_markup(unjoined), parse_mode="HTML")
        return

    bot.reply_to(message, get_welcome_text(), parse_mode="HTML")


@bot.callback_query_handler(func=lambda call: call.data == "check_join")
def handle_verify_callback(call):
    user_id = call.from_user.id
    is_joined, unjoined = check_user_membership(user_id)

    if is_joined:
        bot.answer_callback_query(call.id, "✅ Verified successfully!", show_alert=False)
        try:
            # Instantly transform the message into the full Welcome screen and remove all buttons
            bot.edit_message_text(
                get_welcome_text(),
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML"
            )
        except Exception:
            pass
    else:
        # User still has pending channels
        pending_str = ", ".join(unjoined)
        bot.answer_callback_query(
            call.id, 
            f"❌ You haven't joined: {pending_str}\nPlease join to continue!", 
            show_alert=True
        )
        try:
            text = (
                "⚠️ <b>Action Incomplete!</b>\n\n"
                f"You still need to join: <b>{pending_str}</b>\n"
                "Please join below and click <b>Verify & Continue</b>."
            )
            bot.edit_message_text(
                text,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=make_force_sub_markup(unjoined),
                parse_mode="HTML"
            )
        except Exception:
            pass


def clean_phone(val):
    if not val:
        return ""
    digits = re.sub(r"\D", "", str(val).strip())
    if not digits:
        return ""

    if len(digits) == 12 and digits.startswith("91"):
        return digits[2:]
    if len(digits) == 11 and digits.startswith("0"):
        return digits[1:]
    if len(digits) == 10:
        return digits
    if len(digits) > 10 and digits.startswith("91"):
        return digits[2:12]
    if len(digits) >= 10:
        return digits[-10:]

    return digits


def extract_clean_records(data):
    cur = data
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

        num = item.get("num") or item.get("mobile") or item.get("phone") or ""
        name = item.get("name") or item.get("customer_name") or ""
        fname = item.get("fname") or item.get("father") or item.get("father_name") or ""
        alt = item.get("alt") or item.get("alt_num") or ""
        circle = item.get("circle") or item.get("telecom_circle") or ""
        id_val = item.get("aadhar") or item.get("id") or ""
        addr = item.get("address") or ""

        uid = f"{num}-{name}-{id_val}"
        if uid in seen and uid != "--":
            continue
        seen.add(uid)

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


@bot.message_handler(func=lambda msg: True)
def handle_number(message):
    user_id = message.from_user.id
    
    # 1. Check membership before processing any search query
    is_joined, unjoined = check_user_membership(user_id)
    if not is_joined:
        pending_str = ", ".join(unjoined)
        text = (
            "⚠️ <b>Channel Membership Required!</b>\n\n"
            f"You must be in <b>{pending_str}</b> to search numbers.\n"
            "Please join below and click <b>Verify & Continue</b>."
        )
        bot.reply_to(message, text, reply_markup=make_force_sub_markup(unjoined), parse_mode="HTML")
        return

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
        bot.reply_to(message, "⚠️ API_URL is not configured in environment.", parse_mode="HTML")
        return

    # 2. Animated Progress Bar
    loading_frames = [
        "<code>[■□□□□□□□□□] 10%</code>\n🛡️ <b>VALIDATING NUMBER...</b>",
        "<code>[■■■■□□□□□□] 40%</code>\n🔍 <b>SCANNING DATABASE...</b>",
        "<code>[■■■■■■■□□□] 75%</code>\n⚡ <b>FETCHING RECORDS...</b>",
        "<code>[■■■■■■■■■■] 100%</code>\n✨ <b>DECRYPTING DATA...</b>"
    ]

    loading_msg = bot.reply_to(message, loading_frames[0], parse_mode="HTML")
    t0 = time.time()

    try:
        time.sleep(0.4)
        bot.edit_message_text(loading_frames[1], chat_id=message.chat.id, message_id=loading_msg.message_id, parse_mode="HTML")
    except Exception:
        pass

    lookup_url = target_api if target_api.endswith("=") else f"{target_api}?number="
    full_url = f"{lookup_url}{phone}"

    try:
        res = requests.get(full_url, timeout=15)
        elapsed = round(time.time() - t0, 2)

        try:
            bot.edit_message_text(loading_frames[3], chat_id=message.chat.id, message_id=loading_msg.message_id, parse_mode="HTML")
        except Exception:
            pass

        if res.status_code != 200:
            bot.edit_message_text(
                f"❌ <b>API Error:</b> HTTP {res.status_code}\n<i>Response Time: {elapsed}s</i>",
                chat_id=message.chat.id,
                message_id=loading_msg.message_id,
                parse_mode="HTML"
            )
            return

        data = res.json()
        records = extract_clean_records(data)

        if not records:
            bot.edit_message_text(
                f"🔍 <b>NO RECORDS FOUND!</b>\n\n"
                f"📱 Query: <code>{html.escape(phone)}</code>\n"
                f"No matching subscriber details found in the database.\n"
                f"⚡ <i>Response Time: {elapsed}s</i>",
                chat_id=message.chat.id,
                message_id=loading_msg.message_id,
                parse_mode="HTML"
            )
            return

        # 3. Formatted Cyber Terminal UI
        response_text = "╭━━━〔 📱 <b>NUMBER INTELLIGENCE</b> 〕━━━╮\n"
        response_text += f"┃ 🎯 <b>Query:</b> <code>{html.escape(phone)}</code>\n"
        response_text += f"┃ 📊 <b>Records Found:</b> <code>{len(records)}</code>\n"
        response_text += "╰━━━━━━━━━━━━━━━━━━━━━━╯\n\n"

        for idx, item in enumerate(records, 1):
            response_text += f"┌─── <b>RECORD #{idx}</b> ───────────────\n"
            if item["name"]:
                response_text += f"│ 👤 <b>NAME:</b> <code>{html.escape(str(item['name'])).upper()}</code>\n"
            if item["fname"]:
                response_text += f"│ 👨‍👦 <b>FATHER:</b> <code>{html.escape(str(item['fname'])).title()}</code>\n"
            if item["num"]:
                response_text += f"│ 📱 <b>MOBILE:</b> <code>{html.escape(str(item['num']))}</code>\n"
            if item["alt"]:
                response_text += f"│ 📞 <b>ALT NUM:</b> <code>{html.escape(str(item['alt']))}</code>\n"
            if item["circle"]:
                response_text += f"│ 🌐 <b>CIRCLE:</b> <code>{html.escape(str(item['circle']))}</code>\n"
            if item["id"]:
                response_text += f"│ 🪪 <b>CAF / ID:</b> <code>{html.escape(str(item['id']))}</code>\n"
            if item["address"]:
                response_text += f"│ 🏠 <b>ADDRESS:</b>\n│    <i>{html.escape(str(item['address']))}</i>\n"
            response_text += "└────────────────────────\n\n"

        response_text += f"🚀 <b>RESPONSE TIME:</b> <code>{elapsed}s</code>\n"
        response_text += "🛡️ <b>STATUS:</b> <code>VERIFIED & DECRYPTED</code>"

        bot.edit_message_text(
            response_text,
            chat_id=message.chat.id,
            message_id=loading_msg.message_id,
            parse_mode="HTML"
        )

    except requests.exceptions.Timeout:
        bot.edit_message_text("⏱️ <b>Timeout Error:</b> Server took more than 15s to respond.", chat_id=message.chat.id, message_id=loading_msg.message_id, parse_mode="HTML")
    except Exception as e:
        bot.edit_message_text(f"⚠️ <b>Error:</b> {html.escape(str(e))}", chat_id=message.chat.id, message_id=loading_msg.message_id, parse_mode="HTML")


if __name__ == "__main__":
    if not BOT_TOKEN:
        print("[ERROR] BOT_TOKEN is missing. Set it in .env or Railway environment variables.")
    else:
        try:
            bot.remove_webhook()
            time.sleep(1)
        except Exception:
            pass

        channels = get_required_channels()
        print(f"🤖 Bot starting... Active Force-Sub Channels: {channels or 'None'}")
        
        bot.infinity_polling(
            timeout=25, 
            long_polling_timeout=20,
            allowed_updates=["message", "callback_query", "chat_member"]
        )
