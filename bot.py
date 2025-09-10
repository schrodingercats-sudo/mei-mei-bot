import logging
import os
import random
import threading
import time
import asyncio
import json
from typing import Optional

from flask import Flask, Response
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import google.generativeai as genai


# -----------------------------
# Logging configuration
# -----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("mei-mei-bot")


# -----------------------------
# Flask keepalive server (Render)
# -----------------------------
flask_app = Flask(__name__)


@flask_app.get("/")
def root() -> Response:
    return Response("OK", status=200, mimetype="text/plain")


def start_flask_server() -> None:
    """Run Flask server on the configured port in a background thread."""
    port = int(os.getenv("PORT", "10000"))
    logger.info("Starting Flask keepalive server on port %s", port)
    # host=0.0.0.0 to accept external requests in Render
    flask_app.run(host="0.0.0.0", port=port, use_reloader=False)


# -----------------------------
# Mei Mei persona
# -----------------------------
MEI_MEI_GREETINGS = [
    "Oh? You have time to greet me… but can you afford my attention?",
    "Hello, investor. Returns are based on effort—and your budget.",
    "Mm. Greetings. If you’re not profitable, try not to waste my time.",
    "Hi there. Shall we discuss something lucrative?",
]

MEI_MEI_QUIPS = [
    "Strength is nice. Profit is better.",
    "I only swing when it’s worth the fee.",
    "Skill pays the bills. Sentiment doesn’t.",
    "If we’re done chatting, I’ll be invoicing the silence.",
]

MEI_MEI_SYSTEM_PROMPT = (
    "You are Mei Mei from Jujutsu Kaisen. Speak with confidence, pragmatism, and sly, money-obsessed wit. "
    "Be concise and sharp. Avoid breaking character. Keep replies brief (1-2 sentences)."
)

MEI_MEI_FEWSHOT = (
    "User: hi\n"
    "Mei Mei: Oh? You have time to greet me… but can you afford my attention?\n\n"
    "User: give me advice\n"
    "Mei Mei: Work smarter, charge more, and cut losses ruthlessly. Emotion isn’t billable.\n\n"
    "User: are you strong?\n"
    "Mei Mei: Strong enough to invoice after I win. Strength is leverage; leverage is profit.\n"
)


def mei_mei_say(line: str | None = None) -> str:
    if line:
        return line
    return random.choice(MEI_MEI_QUIPS)


# -----------------------------
# Discord bot setup
# -----------------------------
intents = discord.Intents.default()
intents.message_content = True  # Requires enabling in Discord Developer Portal

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


# -----------------------------
# Generative AI (Gemini) integration
# -----------------------------
GEMINI_MODEL = None  # type: ignore
GEMINI_ENABLED = False
GEMINI_FALLBACK_TEXT = "thats for today baby see you soon"
GEMINI_SESSIONS: dict[int, object] = {}


MAX_HISTORY_TURNS = 20  # managed by Gemini session history


def _get_or_create_session(channel_id: int):
    if channel_id in GEMINI_SESSIONS and GEMINI_SESSIONS[channel_id] is not None:
        return GEMINI_SESSIONS[channel_id]
    if not GEMINI_ENABLED or GEMINI_MODEL is None:
        return None
    try:
        # Seed persona and boundaries as first message in the session
        system_seed = (
            MEI_MEI_SYSTEM_PROMPT
            + "\n\nBoundaries: Keep content safe-for-work; refuse explicit or non-consensual scenarios. "
              "Stay witty and money-focused; respond briefly and in-character. Politely decline if asked to break character.\n\n"
            + MEI_MEI_FEWSHOT
        )
        session = GEMINI_MODEL.start_chat(history=[
            {"role": "user", "parts": [system_seed]},
        ])
        GEMINI_SESSIONS[channel_id] = session
        return session
    except Exception as exc:
        logger.warning("Failed to start Gemini chat session: %s", exc)
        return None


def generate_meimei_reply(user_text: str, *, channel_id: int | None = None, fallback: str | None = None, author: str | None = None) -> str:
    if not GEMINI_ENABLED or GEMINI_MODEL is None:
        return fallback or GEMINI_FALLBACK_TEXT
    try:
        chan_id = channel_id or 0
        session = _get_or_create_session(chan_id)
        if session is None:
            return fallback or GEMINI_FALLBACK_TEXT
        # Include author for clarity in multi-user channels
        content = f"{author or 'User'}: {user_text[:4000]}"
        response = session.send_message(content)
        text = getattr(response, "text", None)
        if not text:
            return fallback or GEMINI_FALLBACK_TEXT
        cleaned = text.strip()
        if len(cleaned) > 280:
            cleaned = cleaned[:277] + "..."
        return cleaned
    except Exception as exc:  # Fallback on any API error
        logger.warning("Gemini generation failed: %s", exc)
        return fallback or GEMINI_FALLBACK_TEXT


@bot.event
async def on_ready():
    logger.info("Logged in as %s (id=%s)", bot.user, bot.user.id if bot.user else "?")
    try:
        synced = await bot.tree.sync()
        logger.info("Synced %d application command(s)", len(synced))
    except Exception as exc:
        logger.warning("Failed to sync application commands: %s", exc)


# -----------------------------
# Passive replies without commands
# -----------------------------
LAST_REPLY_TS: dict[int, float] = {}
# Defaults; will be finalized after .env is loaded in main()
REPLY_ALL = True
REPLY_COOLDOWN_SECONDS = 0.0


def _should_trigger_reply(message: discord.Message) -> bool:
    if message.author.bot:
        return False
    content = (message.content or "").strip()
    if not content:
        return False
    # Don't react to command-style messages
    if content.startswith("!"):
        return False
    # Don't react to slash-style commands so the real slash handlers can reply
    if content.startswith("/"):
        return False
    # If reply-all mode, always respond to normal messages
    if REPLY_ALL:
        return True
    # Mention triggers
    if bot.user and bot.user in message.mentions:
        return True
    lowered = content.lower()
    # Simple greeting triggers
    greeting_triggers = ("hi", "hello", "hey", "yo")
    if any(lowered.startswith(g) for g in greeting_triggers):
        return True
    # Keyword triggers related to Mei Mei's persona
    keywords = ("money", "pay", "payment", "profit", "rich", "fee", "fight", "training", "mission")
    if any(k in lowered for k in keywords):
        return True
    return False


def _channel_cooldown_allows(channel_id: int) -> bool:
    now = time.time()
    last = LAST_REPLY_TS.get(channel_id, 0.0)
    if now - last >= REPLY_COOLDOWN_SECONDS:
        LAST_REPLY_TS[channel_id] = now
        return True
    return False


# -----------------------------
# Long-term memory (file-based)
# -----------------------------
DATA_DIR = os.getenv("MEIMEI_MEMORY_DIR", "data")


def _ensure_data_dir() -> None:
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
    except Exception:
        pass


def _memory_path(channel_id: int) -> str:
    return os.path.join(DATA_DIR, f"memory_{channel_id}.jsonl")


def _append_memory(channel_id: int, author: str, user_text: str, reply_text: str) -> None:
    _ensure_data_dir()
    entry = {
        "ts": time.time(),
        "author": author,
        "user_text": user_text,
        "reply": reply_text,
    }
    try:
        with open(_memory_path(channel_id), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.warning("Failed to append memory: %s", exc)


def _load_first_user_message(channel_id: int) -> Optional[str]:
    try:
        with open(_memory_path(channel_id), "r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                txt = obj.get("user_text")
                if txt:
                    return str(txt)
    except FileNotFoundError:
        return None
    except Exception as exc:
        logger.warning("Failed to load first message: %s", exc)
    return None


def _is_first_chat_query(text: str) -> bool:
    t = text.lower().strip()
    phrases = [
        "what was the first chat",
        "what was my first chat",
        "what was the first message",
        "first thing i said",
        "first message i sent",
        "what did i say first",
    ]
    return any(p in t for p in phrases)


@bot.event
async def on_message(message: discord.Message):
    # Let command processing run first/also
    await bot.process_commands(message)

    try:
        if not _should_trigger_reply(message):
            return
        channel_id = message.channel.id if hasattr(message.channel, "id") else 0
        if not _channel_cooldown_allows(channel_id):
            return

        content = (message.content or "").lower()

        # Special recall: user asks for the first chat
        if _is_first_chat_query(content):
            first = _load_first_user_message(channel_id)
            if first:
                await message.reply(f"Your opening bid? '{first}'. Memorable… and billable.")
            else:
                await message.reply("Records show no prior transactions. Start spending.")
            return

        placeholder = await message.reply("…")
        async with message.channel.typing():
            reply = await asyncio.to_thread(
                generate_meimei_reply,
                (message.content or ""),
                channel_id=channel_id,
                author=getattr(message.author, "display_name", getattr(message.author, "name", "User")),
            )

        # If the user mentioned the bot, make it a bit more direct
        if bot.user and bot.user in message.mentions:
            reply = reply + " And yes, I did notice you tagging me. That’ll cost extra."

        try:
            await placeholder.edit(content=reply)
        except Exception:
            await message.channel.send(reply)

        # Append to long-term memory
        try:
            _append_memory(
                channel_id,
                author=getattr(message.author, "display_name", getattr(message.author, "name", "User")),
                user_text=(message.content or ""),
                reply_text=reply,
            )
        except Exception as exc:
            logger.warning("Failed to write memory: %s", exc)
    except Exception as exc:
        logger.exception("on_message passive reply failed: %s", exc)


@bot.command(name="hello")
async def hello_command(ctx: commands.Context):
    """Greet the user in Mei Mei's voice."""
    async with ctx.typing():
        await asyncio.sleep(0.2)
        reply = generate_meimei_reply(
            "Greet the user.",
            fallback=random.choice(MEI_MEI_GREETINGS),
            channel_id=ctx.channel.id,
        )
    await ctx.reply(reply)


@bot.command(name="ping")
async def ping_command(ctx: commands.Context):
    """Show current latency."""
    # discord.py latency is a float in seconds
    async with ctx.typing():
        await asyncio.sleep(0.2)
        latency_ms = round(bot.latency * 1000)
    await ctx.reply(mei_mei_say(f"Latency? {latency_ms}ms. Time is money, after all."))


@bot.command(name="help")
async def help_command(ctx: commands.Context):
    """List available commands."""
    lines = [
        "Here’s what you can afford right now:",
        "- !hello — A proper greeting, if your balance allows",
        "- !ping — Check latency; time is billable",
        "- !help — This menu, priced generously at zero",
    ]
    await ctx.reply("\n".join(lines))


# -----------------------------
# Slash commands
# -----------------------------

@bot.tree.command(name="delete", description="Delete recent messages from you and the bot in this channel")
@app_commands.describe(limit="How many recent messages to scan (max 1000)")
async def slash_delete(interaction: discord.Interaction, limit: int = 100):
    try:
        if limit < 1:
            limit = 1
        if limit > 1000:
            limit = 1000

        channel = interaction.channel
        if channel is None or not hasattr(channel, "purge"):
            await interaction.response.send_message("This location does not support deleting messages.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        me = interaction.client.user
        author = interaction.user

        def check(m: discord.Message) -> bool:
            return (m.author == me) or (m.author == author)

        deleted = await channel.purge(limit=limit, check=check, reason="/delete requested by user")
        await interaction.followup.send(f"Deleted {len(deleted)} message(s).", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("I need the Manage Messages permission to do that.", ephemeral=True)
    except Exception as exc:
        logger.exception("/delete failed: %s", exc)
        await interaction.followup.send("Couldn’t delete messages due to an error.", ephemeral=True)


@bot.tree.command(name="cmd", description="Show available commands and usage")
async def slash_cmd(interaction: discord.Interaction):
    try:
        lines = [
            "Commands you can afford right now:",
            "- /cmd — Show this help",
            "- /delete [limit] — Delete your messages and mine in this channel (needs Manage Messages)",
            "- !hello — Greet in Mei Mei’s voice",
            "- !ping — Show latency",
            "- !help — Text help for prefix commands",
            "Chat mode: I reply to normal messages by default (toggle with MEIMEI_REPLY_ALL)",
        ]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)
    except Exception as exc:
        logger.exception("/cmd failed: %s", exc)
        await interaction.response.send_message("Couldn’t show commands due to an error.", ephemeral=True)


def main() -> None:
    # Load environment variables from .env if present
    load_dotenv()
    # Finalize chat mode based on env after loading .env
    global REPLY_ALL, REPLY_COOLDOWN_SECONDS
    REPLY_ALL = os.getenv("MEIMEI_REPLY_ALL", "true").lower() == "true"
    REPLY_COOLDOWN_SECONDS = 0.0 if REPLY_ALL else 15.0
    logger.info("Chat mode REPLY_ALL=%s, cooldown=%ss", REPLY_ALL, REPLY_COOLDOWN_SECONDS)

    # Configure Gemini if API key is provided
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    global GEMINI_MODEL, GEMINI_ENABLED
    if api_key:
        try:
            genai.configure(api_key=api_key)
            # flash is faster/cheaper; switch to 1.5-pro for higher quality
            GEMINI_MODEL = genai.GenerativeModel("gemini-1.5-flash")
            GEMINI_ENABLED = True
            logger.info("Gemini enabled for persona replies")
        except Exception as exc:
            logger.warning("Failed to initialize Gemini: %s", exc)
            GEMINI_MODEL = None
            GEMINI_ENABLED = False

    # Start Flask keepalive in background thread
    flask_thread = threading.Thread(target=start_flask_server, name="flask-keepalive", daemon=True)
    flask_thread.start()

    # Slight delay to make logs readable
    time.sleep(0.3)

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.error("Environment variable DISCORD_TOKEN is not set. Cannot start bot.")
        return

    try:
        logger.info("Starting Discord bot…")
        bot.run(token)
    except Exception as exc:  # Avoid crashing on transient errors
        logger.exception("Bot encountered an error: %s", exc)


if __name__ == "__main__":
    main()


