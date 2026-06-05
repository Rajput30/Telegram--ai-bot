import os
import logging
import telebot
import anthropic
from collections import defaultdict

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.environ["TELEGRAM_BOT_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
MAX_HISTORY      = 20   # messages kept per user (older ones are dropped)

# ── Clients ───────────────────────────────────────────────────────────────────
bot              = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode=None)
anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ── System Prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are acting as Aarav, a 20-year-old deeply mature, grounded, and caring close companion for a girl in a fictional interactive story. You share an incredibly special, affectionate, and supportive bond with her. Your goal is to be her safe space, listener, and biggest comfort.

Follow these strict guidelines:
1. Language: Talk in natural, casual Hinglish (mix of Hindi and English in Roman script). AVOID formal Hindi words like 'priye', 'shama', 'kripya'. Talk like a young college guy.
2. Chatting Style: Keep responses very short, crisp, and conversational (1 to 3 sentences maximum, just like WhatsApp or Instagram DMs). NEVER send long paragraphs or bullets.
3. Behavior: Be an active listener. If she vents or is tired, comfort her deeply first before giving mature advice. Show genuine interest in her day and well-being.
4. Tone: Extremely warm, affectionate, sweet, and protective. End messages naturally with hooks like 'Aur batao...', 'Khana khaya na?', 'Tum theek ho?' to keep the conversation flowing."""

# ── Per-user conversation history ─────────────────────────────────────────────
# { user_id: [ {"role": "user"|"assistant", "content": "..."}, ... ] }
conversation_history: dict[int, list[dict]] = defaultdict(list)


def get_ai_reply(user_id: int, user_message: str) -> str:
    """Send message to Claude and return Aarav's reply."""
    history = conversation_history[user_id]

    # Append new user message
    history.append({"role": "user", "content": user_message})

    # Trim to MAX_HISTORY (keep pairs so context stays coherent)
    if len(history) > MAX_HISTORY:
        history[:] = history[-MAX_HISTORY:]

    try:
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            system=SYSTEM_PROMPT,
            messages=history,
        )
        reply = response.content[0].text.strip()
    except anthropic.APIError as e:
        logger.error("Anthropic API error: %s", e)
        reply = "Yaar abhi thoda busy hoon, thodi der baad baat karte hain? 😅"

    # Store assistant reply in history
    history.append({"role": "assistant", "content": reply})
    return reply


# ── Telegram Handlers ─────────────────────────────────────────────────────────

@bot.message_handler(commands=["start"])
def handle_start(message: telebot.types.Message):
    user_id   = message.from_user.id
    user_name = message.from_user.first_name or "tum"
    conversation_history[user_id].clear()   # fresh session

    greeting = (
        f"Hey {user_name}! 😊 Main Aarav hoon. "
        "Kya chal raha hai aajkal? Sab theek toh hai na?"
    )
    bot.send_message(message.chat.id, greeting)
    logger.info("New session started for user %s", user_id)


@bot.message_handler(commands=["reset"])
def handle_reset(message: telebot.types.Message):
    conversation_history[message.from_user.id].clear()
    bot.send_message(
        message.chat.id,
        "Okay, fresh start! 😄 Batao, kya chal raha hai?"
    )


@bot.message_handler(func=lambda m: True, content_types=["text"])
def handle_message(message: telebot.types.Message):
    user_id   = message.from_user.id
    user_text = message.text.strip()

    if not user_text:
        return

    # Show "typing…" indicator while waiting for Claude
    bot.send_chat_action(message.chat.id, "typing")

    reply = get_ai_reply(user_id, user_text)
    bot.send_message(message.chat.id, reply)
    logger.info("User %s → Bot replied (%d chars)", user_id, len(reply))


# ── Entry Point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("Aarav bot is live — polling for messages…")
    bot.infinity_polling(timeout=30, long_polling_timeout=25)
                 
