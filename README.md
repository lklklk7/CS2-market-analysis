# 🎮 CS2 Skin Tracker

## Screenshots

screenshot 1 here

screenshot 2 here

screenshot 3 here

screenshot 4 here

---

AI-powered CS2 skin price analysis system. Pulls market data from Steam, CSFloat, Skinport, and Buff163 daily, runs Claude/GPT analysis, and pushes a decision dashboard to Discord/Slack.

## Quick Start

### GitHub Actions (recommended — zero infra)

1. Fork this repo
2. Go to **Settings → Secrets and variables → Actions** and add:

| Secret | Description |
|--------|-------------|
| `SKIN_LIST` | Comma-separated skin names, e.g. `AK-47 \| Redline (Field-Tested),AWP \| Asiimov (Battle-Scarred)` |
| `ANTHROPIC_API_KEY` | Claude API key (or set `OPENAI_API_KEY`) |
| `DISCORD_WEBHOOK_URL` | Discord channel webhook URL |

3. Enable Actions → manually trigger **Daily CS2 Skin Analysis** to test

Runs automatically every day at **09:00 UTC**.

### Local

```bash
git clone https://github.com/YOUR_USERNAME/cs2-skin-tracker
cd cs2-skin-tracker
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
python main.py
```

### Common commands

```bash
python main.py                                           # run analysis + notify
python main.py --skins "AK-47 | Redline (Field-Tested)" # override watchlist
python main.py --dry-run                                 # skip notifications
python main.py --debug                                   # verbose logging
python main.py --schedule                                # cron loop (local)
python main.py --serve-only                              # web UI only
```

Web UI available at `http://localhost:8000` after `--serve-only`.

## Data Sources

| Source | Data | Auth required |
|--------|------|---------------|
| Steam Market | Current price, 24h volume | None |
| Skinport | Suggested price, avg sale | None (optional key) |
| CSFloat | Float distribution, listings | None (optional key) |
| Buff163 | CN market price | `BUFF_COOKIE` env var |

## Environment Variables

See [`.env.example`](.env.example) for all options.

## Output Example

```
🎮 2026-06-04 CS2 Skin Dashboard
Analyzed 2 skin(s) | 🟢 Buy: 1  🟡 Hold: 1  🔴 Sell: 0

🟢 AK-47 | Redline (Field-Tested) — BUY | Score: 74 | 📈 Rising
🟡 AWP | Asiimov (Battle-Scarred) — HOLD | Score: 52 | ➡️ Sideways
```
