# Netacad Certificate

<img width="1369" height="1060" alt="image" src="https://github.com/user-attachments/assets/981c6061-bf1a-4fa5-8342-97163985530d" />

# Feedback video

https://drive.google.com/file/d/1jbkEN6r60cSsTpluPhTRolLRLgm4qdD-/view?usp=sharing

# Final Project

1. Automated News Aggregator
2. CI/CD with Gitlab

# Quick Start

1. Clone and enter the bot folder
```bash
git clone https://github.com/xerxtye/final-project-infosec
cd final-project-infosec/news_scraper
```

2. Set up `.env`
```bash
cp .env.example .env
```
Edit `.env` and add:
```bash
TELEGRAM_TOKEN=BOT_TELEGRAM_TOKEN
TELEGRAM_CHANNEL=CHANNEL_ID
```
For private channels, use the `-100...` channel id.

3. Edit `config.json`
Keep the feeds there. Example:
```json
{
  "name": "Example",
  "url": "https://example.org/rss.xml"
}
```

4. Run the bot
```bash
python3 main.py
```

# External Sources
[RSS-Bridge](https://github.com/rss-bridge/rss-bridge) — The RSS feed for websites missing it.
