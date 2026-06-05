import os
import logging
import threading
import random
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from openai import OpenAI  # ✅ Groq ki jagah OpenAI library
from collections import defaultdict

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN  = os.environ["TELEGRAM_BOT_TOKEN"]
GITHUB_TOKEN    = os.environ["GITHUB_TOKEN"]  # ✅ GROQ_API_KEY ki jagah GITHUB_TOKEN
MAX_HISTORY     = 20

# ── Clients ───────────────────────────────────────────────────────────────────
bot    = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode=None)
client = OpenAI(                                         # ✅ GitHub Models client
    base_url="https://models.inference.ai.azure.com",
    api_key=GITHUB_TOKEN,
)

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

# ── Sticker IDs ───────────────────────────────────────────────────────────────
STICKERS = {
    "happy": [
        "CAACAgUAAxkBAANBaiKZq7a6s2ntoGYP_m9uk-sAAYcmAAIwBgAC_rrpVPQPpueszCNvOwQ",
        "CAACAgUAAxkBAANFaiKZvQKVdCHLJqKWoBDS58Z_opYAAt8DAAKtXwhXYh6k0KzDdiE7BA",
        "CAACAgUAAxkBAANjaiKaBjoYSrEzsrjSJB_BG5mIW3oAAmQQAAJo4ZBXpZT6Ij5qmlw7BA",
        "CAACAgUAAxkBAANpaiKaFY5DDQWVutRH9ndPQngPirAAAoERAAJxqZhXzTmnNgpLxMc7BA",
    ],
    "love": [
        "CAACAgUAAxkBAAM9aiKZpUE2dVB9PJzmYnxrEAZ3tiQAAjYDAAJevblVgC5idGq3pig7BA",
        "CAACAgUAAxkBAANHaiKZwotcWjMGvfearEicjzuZhQIAAi4EAAL2twlXZAKl9FV9LLU7BA",
        "CAACAgUAAxkBAANhaiKaAAH8lncr2T7ZeEEAAWn8rrvD6wACGBEAAmwVkVcc8GHeclkNAzsE",
        "CAACAgUAAxkBAANnaiKaEaLeGEo0oVnDGzC_CzHLZBMAAtMVAAKqxkBVQ4EIjKIET9k7BA",
    ],
    "sad": [
        "CAACAgUAAxkBAANDaiKZs_FU4k8aVy0HHZ09_2TcL60AAv0CAALKKxBXPYyeZPEWva07BA",
        "CAACAgUAAxkBAAN_aiKZp3_mukSuGHyiCZP4lXawzU4AAncDAAJ6R7lVwLrAJDD28PU7BA",
        "CAACAgUAAxkBAAMxaiKZhptliUHDw4k4mLeFtjk6SiIAAksTAALOdZFXwSuj_MO5Dkk7BA",
        "CAACAgUAAxkBAANbaiKZ97Ca8VUfdrSxM9klGi6wCRUAAvsTAAK-lZFXGzydHinh5Aw7BA",
    ],
    "funny": [
        "CAACAgUAAxkBAANJaiKZxy76VlN_OLPLQTHHORXeOn0AAvICAAJSRqhWjZhalx0Mk-Q7BA",
        "CAACAgUAAxkBAANLaiKZy6iGde8dZel3m2V5WJy1yI4AAoQEAAKgqBBXvVYpEO19LFI7BA",
        "CAACAgUAAxkBAANNaiKZ0IggFALjZP90MtP3gqaHL0oAAlgEAAIu1hBXskX9LoEfEFk7BA",
        "CAACAgUAAxkBAANfaiKZ-6U2UQVXRX1fd5qsuwSIaKgAAk0TAAKXw0BVXQJQD7hvZIg7BA",
    ],
    "angry": [
        "CAACAgUAAxkBAANPaiKZ1qhzbBO_Vo0dT_gKTpX-ycgAApYEAAK6MxBXoUgzduK86JA7BA",
        "CAACAgUAAxkBAANTaiKZ4GVC0kwOY4s0xbxbbclfXOoAAigQAALq15BX2ozQVRZKXPI7BA",
        "CAACAgUAAxkBAANVaiKZ4oI15FczTLilvIAjrfduuy8AAlQSAALlnJBXw0lFtW6peGg7BA",
        "CAACAgUAAxkBAANraiKaGaoqgBfANScE5Kb_VB_OewcAAtkRAALk5ZBX_aUD4NctHkE7BA",
    ],
    "neutral": [
        "CAACAgUAAxkBAANXaiKZ5f3c8V1KzushVeUW54DlMbMAAjASAALexZlXfFPo2Qf1S_Y7BA",
        "CAACAgUAAxkBAANZaiKZ6Dg4pIDNBZG1qG6dSWgf__YAAkoPAAKPpZlXFImY9lBurSU7BA",
        "CAACAgUAAxkBAANdaiKZ9QIru0kT6uI6sAW9OX2z-AADiQ8AAg5XmFdzxFUCtZYU2DsE",
        "CAACAgUAAxkBAANlaiKaDaE0726nVeP_LvcFo8Q8k1IAAioWAAJjakFVoidGaEWYHLg7BA",
    ],
}


def get_random_sticker(mood: str = "neutral") -> str:
    stickers = STICKERS.get(mood, STICKERS["neutral"])
    return random.choice(stickers)


# ── Per-user conversation history ─────────────────────────────────────────────
conversation_history: dict[int, list[dict]] = defaultdict(list)


def get_ai_reply(user_id: int, user_message: str) -> str:
    history = conversation_history[user_id]
    history.append({"role": "user", "content": user_message})

    if len(history) > MAX_HISTORY:
        history[:] = history[-MAX_HISTORY:]

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # ✅ GitHub Models ka free GPT-4o-mini
            max_tokens=300,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history,
        )
        reply = response.choices[0].message.content.strip()
    except Exception as e:
        logger.error("GitHub Models API error: %s", e)
        reply = "Yaar abhi thoda busy hoon, thodi der baad baat karte hain? 😅"

    history.append({"role": "assistant", "content": reply})
    return reply


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
    bot.send_sticker(message.chat.id, get_random_sticker("happy"))
    logger.info("New session started for user %s", user_id)


@bot.message_handler(commands=["reset"])
def handle_reset(message: telebot.types.Message):
    conversation_history[message.from_user.id].clear()
    bot.reply_to(message, "Okay, fresh start! 😄 Batao, kya chal raha hai?")


@bot.message_handler(content_types=["sticker"])
def handle_sticker(message: telebot.types.Message):
    user_id = message.from_user.id

    if message.chat.type in ["group", "supergroup"]:
        bot_id = bot_info.id
        replied_to_bot = (
            message.reply_to_message is not None and
            message.reply_to_message.from_user is not None and
            message.reply_to_message.from_user.id == bot_id
        )
        if not replied_to_bot:
            return

    bot.send_chat_action(message.chat.id, "typing")
    reply = get_ai_reply(user_id, "maine tumhe ek sticker bheja 🎭")
    bot.reply_to(message, reply)
    bot.send_sticker(message.chat.id, get_random_sticker("happy"))
    logger.info("User %s → Sticker received, bot replied", user_id)


@bot.message_handler(func=lambda m: True, content_types=["text"])
def handle_message(message: telebot.types.Message):
    user_id   = message.from_user.id
    user_text = message.text.strip()

    if not user_text:
        return

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

    # 30% chance sticker bhi bheje
    if random.random() < 0.3:
        bot.send_sticker(message.chat.id, get_random_sticker("neutral"))

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
