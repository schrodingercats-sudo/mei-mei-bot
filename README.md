### Mei Mei Discord Bot

A Discord bot built with `discord.py` that roleplays as Mei Mei from Jujutsu Kaisen, with a Flask keepalive server for Render hosting.

#### Features
- `!hello` — Mei Mei-style greeting
- `!ping` — Shows latency
- `!help` — Lists commands
- Always responds in-character with witty, money-obsessed quips

#### Requirements
- Python 3.10+
- A Discord Bot Token stored in environment variable `DISCORD_TOKEN`
 - Optional: Google Gemini API key via `GEMINI_API_KEY` for richer persona replies

Note: On Python 3.13, you may see `ModuleNotFoundError: No module named 'audioop'`. This project pins a compatibility package (`audioop-lts`) to satisfy `discord.py`'s optional import path; the bot remains chat-only and does not use voice/audio.

#### Local Setup (Windows PowerShell)
1. Clone or create the project folder.
2. Create and activate a virtual environment:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
3. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
4. Configure environment variables (choose one):
   - Using `.env` file (recommended):
     - Copy `env.example` to `.env` and fill in your token:
       ```powershell
       copy env.example .env
       notepad .env
       ```
   - OR set for current session only:
       ```powershell
       $env:DISCORD_TOKEN = "<your_bot_token>"
       ```
5. Run the bot:
   ```powershell
   python bot.py
   ```

#### Optional: Enable Gemini persona replies
- Get an API key from Google AI Studio.
- Add it to `.env`:
  ```env
  GEMINI_API_KEY=your_key_here
  ```
The bot will use Gemini (model `gemini-1.5-flash`) to keep replies brief and in-character. If the key is absent or an error occurs, it falls back to built-in lines.

#### Discord Configuration
- In the Discord Developer Portal:
  - Enable the "Message Content Intent" if you want the bot to read message content.
  - Generate an OAuth2 URL with bot scope and permissions (e.g., `Send Messages`).
  - Invite the bot to your server using that URL.

#### Deploy on Render
1. Push this project to a GitHub repository.
2. On Render, create a new Web Service and connect the repo.
3. Settings:
   - Build command: `pip install -r requirements.txt`
   - Start command: provided via `Procfile` (`web: python bot.py`)
   - Environment Variable: `DISCORD_TOKEN` = your token
4. After deploy, the service exposes `GET /` responding `OK` on port `10000`, and the bot connects to Discord.

#### Notes
- Do not commit your token.
- Rotate the token if leaked.
- Update persona lines in `bot.py` to keep responses fresh.
 - Toggle chat behavior with `MEIMEI_REPLY_ALL=true|false` in `.env`.

