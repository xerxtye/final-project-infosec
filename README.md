# Netacad Certificate

<img width="1369" height="1060" alt="image" src="https://github.com/user-attachments/assets/981c6061-bf1a-4fa5-8342-97163985530d" />

# Feedback video

https://drive.google.com/file/d/1WDjE_698qxlmKABiUT9NmWpILFSTAhpy/view?usp=sharing

# Final Project

1. Automated News Aggregator
2. CI/CD with Gitlab

# Quick Start

1. Modify Config Json
```json
"telegram_token": "BOT_TELEGRAM_TOKEN"
"telegram_channel": "CHANNEL_ID",
```
*for private channels the channel id should start from "-100*CHANNEL_ID"

Add feeds, for instance:
```json
  {
    "name": "Example",
    "url": "https://example.org/rss.xml"
  }
```

2. Run the application
```bash
git clone https://github.com/xerxtye/final-project-infosec
cd final-project-infosec
python3 main.py
```

# External Sources
[RSS-Bridge](https://github.com/rss-bridge/rss-bridge) — The RSS feed for websites missing it.
