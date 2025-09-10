### Mei Mei Discord Bot – Product Requirements & Workflow  

#### Goal  
Build a production-ready Discord bot in Python using `discord.py` that roleplays as Mei Mei from Jujutsu Kaisen. The bot must be easy to deploy on Render via GitHub.  

#### Functional Requirements  
- **Core Commands**:  
  - `!hello`: Greets in Mei Mei’s voice.  
  - `!ping`: Returns latency.  
  - `!help`: Lists available commands and usage.  
- **Style & Tone**: All replies use Mei Mei’s confident, pragmatic, slyly playful, money-obsessed persona. Example: On "hi", reply: "Oh? You have time to greet me… but can you afford my attention?"  
- **Personality Layer**:  
  - Maintain a curated list of Mei Mei-style quips and pick randomly where appropriate (greetings, fallback replies, reaction to unknown commands).  
  - Ensure responses are concise, witty, and consistent.  

#### Non-Functional Requirements  
- **Configuration**: Read Discord token from env var `DISCORD_TOKEN`. No token hardcoding.  
- **Uptime (for Render)**: Run a lightweight Flask web server on port `10000` serving `GET / -> 200 OK` with body `OK` to keep the service warm.  
- **Resilience**:  
  - Handle network/connectivity exceptions without crashing the process.  
  - Log startup, command usage, and errors to stdout/stderr.  
- **Security**:  
  - Do not echo or log secrets.  
  - Validate intents and limit privileged permissions.  

#### Tech Stack  
- Python 3.10+  
- Libraries: `discord.py`, `flask`  

#### Project Structure  
- `bot.py` – Discord client, command handlers, Mei Mei persona layer, and Flask keepalive.  
- `requirements.txt` – Python dependencies.  
- `Procfile` – Render start command (`web: python bot.py`).  
- `README.md` – Setup, environment variables, local run, and Render deployment instructions.  

#### Acceptance Criteria  
- Providing `DISCORD_TOKEN` allows the bot to join a server and respond to `!hello`, `!ping`, and `!help`.  
- Randomized persona responses feel in-character and vary across interactions.  
- Hitting `GET /` on port `10000` returns `200 OK` with body `OK` while the bot remains active.  
- Deploying to Render with the provided files runs successfully without code changes.  

---  

### Implementation Workflow  

#### 1) Initialize Project  
- Create files: `bot.py`, `requirements.txt`, `Procfile`, `README.md`.  
- Add `.gitignore` for `__pycache__/`, `.venv/`, and local `.env`.  

#### 2) Implement Bot  
- In `bot.py`:  
  - Import `os`, `random`, `logging`, `discord`, `flask`.  
  - Configure logging to stdout.  
  - Define Mei Mei persona lines (greetings, quips, fallbacks).  
  - Set up Discord intents minimally (messages, message content if needed).  
  - Register commands `!hello`, `!ping`, `!help`.  
  - Always craft responses in Mei Mei’s tone, using random persona lines when fitting.  
  - Start Flask app on port `10000` returning `OK` at `/`.  
  - Read `DISCORD_TOKEN` from env, error if missing.  

#### 3) Dependencies  
- `requirements.txt`:  
  - `discord.py`  
  - `flask`  

#### 4) Process File  
- `Procfile`:  
  - `web: python bot.py`  

#### 5) Local Run  
- Create and activate a virtual environment.  
- `pip install -r requirements.txt`  
- Set env var `DISCORD_TOKEN` (PowerShell):  
  - `$env:DISCORD_TOKEN = "<your_bot_token>"`  
- Run:  
  - `python bot.py`  
- Invite bot to a Discord server using the OAuth2 URL from the Developer Portal (requires proper intents and permissions).  

#### 6) Deploy to Render  
- Push code to a new GitHub repository.  
- On Render:  
  - Create a new Web Service connected to the repo.  
  - Environment: `Python 3`  
  - Build command: `pip install -r requirements.txt`  
  - Start command: from `Procfile` (`web: python bot.py`).  
  - Environment Variable: `DISCORD_TOKEN` (value: your token).  
- After deploy, verify logs show bot logged in and `GET /` returns `OK`.  

#### 7) Verification Checklist  
- `!hello` returns a witty Mei Mei greeting.  
- `!ping` returns latency in ms.  
- `!help` lists commands and notes the persona.  
- Unknown messages can receive optional in-character quips (if implemented).  
- Flask endpoint `/` returns `OK` and keeps service alive on port `10000`.  

#### 8) Maintenance  
- Rotate `DISCORD_TOKEN` if compromised.  
- Update persona lines periodically to avoid repetition.  
- Pin dependency versions after initial testing for stability.  

---  

This document is the single source of truth for scope and execution for the Mei Mei Discord bot project.  