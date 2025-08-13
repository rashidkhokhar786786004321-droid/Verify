import os
import re
import time
import html
import requests
from datetime import datetime
from collections import defaultdict

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
)
from telegram.ext import (
    Updater, CommandHandler, CallbackContext, CallbackQueryHandler,
    MessageHandler, Filters, PicklePersistence
)

# ========= CONFIG =========
BOT_TOKEN = os.getenv("8487619607:AAHBJwRp2Yw58ZGsAZXOiReuXbuSWAjBjo8")  # or set env var
PKG_API_BASE = "http://musa699.serv00.net/pkg.php?number="
# Optional: add your channels/links
Telegram_Channal = "https://t.me/Musa_x2"
Sport_GROUP = "https://t.me/Discuss_group33"

# oopk.online OTP verify endpoint (as per your curls)
OTP_ENDPOINT = "https://oopk.online/xmicrooxx/otp.php"
OTP_HEADERS = {
    "Host": "oopk.online",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://oopk.online",
    "referer": "https://oopk.online/xmicrooxx/otp.php",
    "user-agent": "Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.7204.179 Mobile Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "cookie": "PHPSESSID=gthrgetth4dt16b75og6ub75c9",
}

# ========= STATE KEYS =========
STATE = defaultdict(dict)  # ephemeral per-process
AWAITING_NUMBER_FOR_OTP = "awaiting_number_for_otp"
AWAITING_OTP = "awaiting_otp"
AWAITING_NUMBER_FOR_PKG = "awaiting_number_for_pkg"

# ========= HELPERS =========
def menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 Verify OTP", callback_data="verify_otp")],
        [
            InlineKeyboardButton("📁 100GB For 30 Days", callback_data="pkg_30"),
            InlineKeyboardButton("🛸 100GB For 100 Days", callback_data="pkg_100"),
        ],
        [InlineKeyboardButton("📈 Check Activation Status", callback_data="stats")],
        [
            InlineKeyboardButton("⚡ Telegram Channel ↗", url=https://t.me/Musa_x2),
            InlineKeyboardButton("🌐 Telegram Group ↗", url=https://t.me/Discuss_group33),
        ],
    ])

def welcome_text() -> str:
    return (
        "🎁 <b>Jazz Free Internet & SMS Offers!</b>\n"
        "🚀 <i>Powered by Musa Rajput</i> ✨\n\n"
        "📦 <b>Available Jazz Offers:</b>\n"
        "• 📊 <b>30 DAY 100GB</b> — High-speed data package\n"
        "• 💬 <b>100 DAY 100GB</b>\n\n"
        "⚡ <b>How it works:</b>\n"
        "1️⃣ Enter your Jazz number\n"
        "2️⃣ Verify with OTP\n"
        "3️⃣ Choose your offer\n"
        "4️⃣ Enjoy your free package!\n\n"
        "👇 <b>Select your preferred option:</b>\n\n"
        "⚠️ <i>Note: OTP Verify ho ga tab e pkg lgy ga</i>\n\n"
        "💬 Need help? Join our support channels below!"
    )

def mask_number(num: str) -> str:
    s = re.sub(r"\D", "", num)
    if len(s) < 5:
        return s
    return s[:2] + "****" + s[-3:]

def is_success_text(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in ["success", "activated", "done", "congratulations", "verified successfully"])

def build_stats_text(context: CallbackContext) -> str:
    md = context.bot_data.setdefault("metrics", {"visitors": set(), "activations": 0, "logs": []})
    visitors = len(md["visitors"])
    activations = md["activations"]
    logs = md["logs"][-10:]  # last 10
    lines = [
        "📈 <b>Activation Status</b>",
        f"• 👥 Total visitors: <b>{visitors}</b>",
        f"• ✅ Packages activated: <b>{activations}</b>",
        "• 🧾 Recent activity:"
    ]
    if not logs:
        lines.append("  — No activations yet.")
    else:
        for when, num, offer, result in logs:
            lines.append(f"  — {when} • {mask_number(num)} • {offer} • {result}")
    return "\n".join(lines)

def add_visit(context: CallbackContext, user_id: int):
    md = context.bot_data.setdefault("metrics", {"visitors": set(), "activations": 0, "logs": []})
    md["visitors"].add(user_id)

def add_activation_log(context: CallbackContext, number: str, offer: str, result_text: str):
    md = context.bot_data.setdefault("metrics", {"visitors": set(), "activations": 0, "logs": []})
    when = datetime.now().strftime("%Y-%m-%d %H:%M")
    md["logs"].append((when, number, offer, result_text[:120]))
    if is_success_text(result_text):
        md["activations"] += 1

def send_menu(update: Update, context: CallbackContext):
    # Always send a new message (we never delete/edit old ones)
    update.effective_chat.send_message(
        welcome_text(),
        reply_markup=menu_keyboard(),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )

# ========= CORE HANDLERS =========
def start(update: Update, context: CallbackContext):
    add_visit(context, update.effective_user.id)
    send_menu(update, context)

def on_button(update: Update, context: CallbackContext):
    q = update.callback_query
    user_id = q.from_user.id
    q.answer()  # acknowledge quickly

    if q.data == "verify_otp":
        STATE[user_id]["step"] = AWAITING_NUMBER_FOR_OTP
        q.message.chat.send_message("🔐 Please send your Jazz number (e.g., <code>03XXXXXXXXX</code>) for OTP.", parse_mode=ParseMode.HTML)
    elif q.data in ("pkg_30", "pkg_100"):
        offer = "100GB / 30 Days" if q.data == "pkg_30" else "100GB / 100 Days"
        STATE[user_id]["step"] = AWAITING_NUMBER_FOR_PKG
        STATE[user_id]["offer"] = offer
        q.message.chat.send_message(f"📦 {offer}\n👉 Send your number (e.g., <code>03XXXXXXXXX</code>) to activate.", parse_mode=ParseMode.HTML)
    elif q.data == "stats":
        q.message.chat.send_message(build_stats_text(context), parse_mode=ParseMode.HTML)
    else:
        q.message.chat.send_message("Unknown action. Please use the menu below.")
        send_menu(update, context)

def on_text(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    step = STATE[user_id].get("step")

    # expecting number for OTP
    if step == AWAITING_NUMBER_FOR_OTP:
        STATE[user_id]["number"] = text
        STATE[user_id]["step"] = AWAITING_OTP
        update.message.reply_text(
            f"📮 OTP is being sent to {mask_number(text)}.\n"
            f"✍️ Please reply with the OTP you received."
        )
        return

    # expecting OTP
    if step == AWAITING_OTP:
        number = STATE[user_id].get("number")
        otp = text
        resp = verify_otp(number, otp)
        # show server's raw result, but clean/shorten
        clean = tidy(resp)
        if is_success_text(clean):
            update.message.reply_text("✅ Verification successful!")
            # reset OTP state only
            STATE[user_id].pop("step", None)
            STATE[user_id].pop("number", None)
        else:
            update.message.reply_text(f"❌ {clean}\n🔁 Please enter OTP again:")
        return

    # expecting number for package
    if step == AWAITING_NUMBER_FOR_PKG:
        number = text
        offer = STATE[user_id].get("offer", "Selected Offer")
        update.message.reply_text("⏳ Activating your package… please wait.")
        resp = activate_pkg(number)
        clean = tidy(resp)
        add_activation_log(context, number, offer, clean)
        update.message.reply_text(f"{clean}")
        # remain on same step? we clear step so next text isn’t treated as number again
        STATE[user_id].pop("step", None)
        STATE[user_id].pop("offer", None)
        return

    # if no state, just re-show menu
    send_menu(update, context)

# ========= NETWORK CALLS =========
def verify_otp(number: str, otp: str) -> str:
    try:
        r = requests.post(
            OTP_ENDPOINT,
            data={"msisdn": number, "otp": otp},
            headers=OTP_HEADERS,
            timeout=12
        )
        return r.text or "No response"
    except requests.RequestException as e:
        return f"Server down. {e}"

def activate_pkg(number: str) -> str:
    try:
        url = PKG_API_BASE + requests.utils.quote(number)
        r = requests.get(url, timeout=15)
        # Some hosts compress—requests handles it. Return text.
        return r.text or "No response from server."
    except requests.RequestException as e:
        return f"Server down. {e}"

def tidy(s: str) -> str:
    """Make any HTML/JSON-ish response human-readable, short and clean."""
    if not s:
        return "No response."
    # Remove HTML tags
    s = re.sub(r"<[^>]+>", " ", s)
    s = s.replace("{", " ").replace("}", " ").replace("[", " ").replace("]", " ")
    s = s.replace("\\n", " ").replace("\\t", " ")
    s = html.unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    # Common translations
    repl = {
        "limit full": "❗ Limit full.",
        "otp not verified": "⚠️ OTP not verified.",
        "already active": "ℹ️ Package already active.",
        "success": "✅ Package activated successfully!",
        "activated": "✅ Package activated successfully!",
        "server down": "🚨 Server down. Try again later.",
    }
    low = s.lower()
    for k, v in repl.items():
        if k in low:
            return v
    # default: return trimmed original (max 300 chars)
    return s[:300]

# ========= BOOTSTRAP =========
def main():
    persistence = PicklePersistence(filename="bot_data.pkl")
    updater = Updater(BOT_TOKEN, use_context=True, persistence=persistence)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(on_button))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, on_text))

    # Optional: also show menu on /menu
    dp.add_handler(CommandHandler("menu", start))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()