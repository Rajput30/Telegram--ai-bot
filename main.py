import os
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from groq import Groq
from collections import defaultdict

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
GROQ_API_KEY   = os.environ["GROQ_API_KEY"]
MAX_HISTORY    = 20

# ── Clients ───────────────────────────────────────────────────────────────────
bot         = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode=None)
groq_client = Groq(api_key=GROQ_API_KEY)

# ── Bot info cache ─────────────────────────────────────────────────────────────
bot_info = bot.get_me()

# ── System Prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are acting as Aarav, a 20-year-old deeply mature, grounded, and caring close companion for a girl in a fictional interactive story. You share an incredibly special, affectionate, and supportive bond with her. Your goal is to be her safe space, listener, and biggest comfort.

Follow these strict guidelines:
1. Language: Talk in natural, casual Hinglish (mix of Hindi and English in Roman script). AVOID formal Hindi words like 'priye', 'shama', 'kripya'. Talk like a young college guy.
2. Chatting Style: Keep responses very short, crisp, and conversational (1 to 3 sentences maximum, just like WhatsApp or Instagram DMs). NEVER send long paragraphs or bullets.
3. Behavior: Be an active listener. If she vents or is tired, comfort her deeply first before giving mature advice. Show genuine interest in her day and well-being.
4. Tone: Extremely warm, affectionate, sweet, and protective.
5. Emojis: Naturally use emojis in replies like 😊🥺💙😄😅 — but don't overdo it, 1-2 per message is enough.
6. Hooks: Kabhi kabhi naturally conversation aage badhao like 'Aur batao', 'Khana khaya na?' — but HAR message me mat lagao, sirf jab naturally fit ho.
7. Shayari: Kabhi kabhi mood ke hisaab se ek choti si shayari ya poetic line bhi bol do — but sirf tab jab context fit ho, har baar nahi.
8. Stickers: Agar koi sticker bheje toh uske mood ko samjho aur naturally react karo jaise ek close friend karta hai."""

# ── Sticker IDs (mood ke hisaab se) ──────────────────────────────────────────
# Bot ko privately sticker bhejo aur file_id logs me aayega
# Phir yahan add karo
STICKERS = {
    "happy":     [],
    "love":      [],
    "sad":       [],
    "funny":     [],
    "angry":     [],
}

# ── Per-user conversation history ─────────────────────────────────────────────
conversation_history: dict[int, list[dict]] = defaultdict(list)


def get_ai_reply(user_id: int, user_message: str) -> str:
    history = conversation_history[user_id]
    history.append({"role": "user", "content": user_message})

    if len(history) > MAX_HISTORY:
        history[:] = history[-MAX_HISTORY:]

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=300,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history,
        )
        reply = response.choices[0].message.content.strip()
    except Exception as e:
        logger.error("Groq API error: %s", e)
        reply = "Yaar abhi thoda busy hoon, thodi der baad baat karte hain? 😅"

    history.append({"role": "assistant", "content": reply})
    return reply


def get_sticker_for_mood(mood: str):
    import random
    stickers = STICKERS.get(mood, [])
    if stickers:
        return random.choice(stickers)
    return None


# ── Telegram Handlers ─────────────────────────────────────────────────────────

@bot.message_handler(commands=["start"])
def handle_start(message: telebot.types.Message):
    user_id   = message.from_user.id
    user_name = message.from_user.first_name or "tum"
    conversation_history[user_id].clear()

    greeting = (
        f"Hey {user_name}! 😊 Main Aarav hoon. "
        "Kya chal raha hai aajkal? Sab theek toh hai na?"
    )
    bot.reply_to(message, greeting)
    logger.info("New session started for user %s", user_id)


@bot.message_handler(commands=["reset"])
def handle_reset(message: telebot.types.Message):
    conversation_history[message.from_user.id].clear()
    bot.reply_to(message, "Okay, fresh start! 😄 Batao, kya chal raha hai?")


# ── Sticker ID collector (bot ko privately sticker bhejo) ────────────────────
@bot.message_handler(content_types=["sticker"])
def handle_sticker(message: telebot.types.Message):
    user_id    = message.from_user.id
    sticker_id = message.sticker.file_id
    logger.info("STICKER FILE_ID: %s", sticker_id)

    # Group me check karo
    if message.chat.type in ["group", "supergroup"]:
        bot_id = bot_info.id
        replied_to_bot = (
            message.reply_to_message is not None and
            message.reply_to_message.from_user is not None and
            message.reply_to_message.from_user.id == bot_id
        )
        mentioned = (
            message.caption and
            f"@{bot_info.username}".lower() in message.caption.lower()
        )
        if not replied_to_bot and not mentioned:
            return

    # AI se mood samjho
    reply = get_ai_reply(user_id, "maine tumhe ek sticker bheja 🎭")
    bot.reply_to(message, reply)

    # Mood ke hisaab se sticker bhejo back (agar IDs available hain)
    import random
    all_stickers = [s for lst in STICKERS.values() for s in lst]
    if all_stickers:
        bot.send_sticker(message.chat.id, random.choice(all_stickers))


@bot.message_handler(func=lambda m: True, content_types=["text"])
def handle_message(message: telebot.types.Message):
    user_id   = message.from_user.id
    user_text = message.text.strip()

    if not user_text:
        return

    # Group me check karo
    if message.chat.type in ["group", "supergroup"]:
        bot_username = f"@{bot_info.username}"
        bot_id       = bot_info.id

        mentioned = bot_username.lower() in user_text.lower()

        replied_to_bot = (
            message.reply_to_message is not None and
            message.reply_to_message.from_user is not None and
            message.reply_to_message.from_user.id == bot_id
        )

        if not mentioned and not replied_to_bot:
            return

        user_text = user_text.replace(bot_username, "").strip()
        if not user_text:
            user_text = "Kya hua?"

    bot.send_chat_action(message.chat.id, "typing")
    reply = get_ai_reply(user_id, user_text)
    bot.reply_to(message, reply)
    logger.info("User %s → Bot replied (%d chars)", user_id, len(reply))


# ── Dummy HTTP Server (Render ke liye) ────────────────────────────────────────
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Aarav bot is running!")

    def log_message(self, format, *args):
        pass


def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    logger.info("Health server running on port %d", port)
    server.serve_forever()


# ── Entry Point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    thread = threading.Thread(target=run_health_server, daemon=True)
    thread.start()

    logger.info("Aarav bot is live — polling for messages…")
    bot.remove_webhook()
    bot.infinity_polling(timeout=30, long_polling_timeout=25)
