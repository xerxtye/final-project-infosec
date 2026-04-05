#!/usr/bin/env python3
import hashlib
import json
import os
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any, Dict, List, Optional


USER_AGENT = "Mozilla/5.0 (compatible; NewsBot/1.0)"


def load_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_url(url: str, timeout: int = 12) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", unescape(text or "")).strip()


def fetch_rss(url: str, max_items: int = 10) -> List[Dict[str, str]]:
    stories: List[Dict[str, str]] = []
    raw = fetch_url(url)
    root = ET.fromstring(raw)

    items = root.findall(".//item")
    if not items:
        entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        for entry in entries[:max_items]:
            title = (entry.findtext("{http://www.w3.org/2005/Atom}title", "") or "").strip()
            link_el = entry.find("{http://www.w3.org/2005/Atom}link")
            link = (link_el.attrib.get("href", "") if link_el is not None else "").strip()
            desc = (entry.findtext("{http://www.w3.org/2005/Atom}summary", "") or "").strip()
            pub = (entry.findtext("{http://www.w3.org/2005/Atom}updated", "") or "").strip()
            if title and link:
                stories.append({
                    "title": unescape(title),
                    "url": link,
                    "desc": strip_html(desc)[:200],
                    "pub": pub,
                })
        return stories

    for item in items[:max_items]:
        title = (item.findtext("title", "") or "").strip()
        link = (item.findtext("link", "") or "").strip()
        desc = (item.findtext("description", "") or "").strip()
        pub = (item.findtext("pubDate", "") or item.findtext("published", "") or "").strip()
        if title and link:
            stories.append({
                "title": unescape(title),
                "url": link,
                "desc": strip_html(desc)[:200],
                "pub": pub,
            })
    return stories


def story_hash(title: str) -> str:
    clean = re.sub(r"[^a-z0-9 ]", "", title.lower().strip())
    return hashlib.md5(clean[:80].encode("utf-8")).hexdigest()[:12]


def parse_date(pub_date_str: str) -> Optional[datetime]:
    if not pub_date_str:
        return None
    try:
        dt = parsedate_to_datetime(pub_date_str.strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    formats = [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(pub_date_str.strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def is_fresh(pub_date_str: str, max_hours: int = 1) -> bool:
    dt = parse_date(pub_date_str)
    if dt is None:
        return True
    age = datetime.now(timezone.utc) - dt
    return age.total_seconds() < (max_hours * 3600)


def extract_og_image(url: str) -> Optional[str]:
    try:
        html = fetch_url(url, timeout=8)[:120000].decode("utf-8", errors="ignore")
        patterns = [
            r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\'](https?://[^"\']+)["\']',
            r'<meta[^>]*content=["\'](https?://[^"\']+)["\'][^>]*property=["\']og:image["\']',
            r'<meta[^>]*name=["\']twitter:image["\'][^>]*content=["\'](https?://[^"\']+)["\']',
        ]
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return match.group(1)
    except Exception:
        return None
    return None


def escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def build_message(story: Dict[str, str], source_name: str) -> str:
    title = escape_html(story["title"])
    desc = escape_html(story.get("desc", ""))
    url = escape_html(story["url"])
    source = escape_html(source_name)

    parts = [f"<b>{title}</b>"]
    if desc:
        parts.append(desc)
    parts.append(f"Source: {source}")
    parts.append(f'<a href="{url}">Read more</a>')
    return "\n\n".join(parts)


def telegram_request(token: str, method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    url = f"https://api.telegram.org/bot{token}/{method}"
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def post_to_telegram(token: str, channel: str, text: str, image_url: Optional[str] = None) -> bool:
    payload: Dict[str, Any]
    method: str

    if image_url:
        method = "sendPhoto"
        payload = {
            "chat_id": channel,
            "photo": image_url,
            "caption": text[:1024],
            "parse_mode": "HTML",
        }
    else:
        method = "sendMessage"
        payload = {
            "chat_id": channel,
            "text": text[:4096],
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }

    try:
        resp = telegram_request(token, method, payload)
        return bool(resp.get("ok", False))
    except Exception:
        if image_url:
            try:
                resp = telegram_request(token, "sendMessage", {
                    "chat_id": channel,
                    "text": text[:4096],
                    "parse_mode": "HTML",
                    "disable_web_page_preview": False,
                })
                return bool(resp.get("ok", False))
            except Exception:
                return False
        return False


def is_near_duplicate(new_title: str, existing_titles: List[str], threshold: float = 0.7) -> bool:
    words_new = set(re.findall(r"\w+", new_title.lower()))
    if not words_new:
        return False
    for existing in existing_titles:
        words_ex = set(re.findall(r"\w+", existing.lower()))
        if not words_ex:
            continue
        overlap = len(words_new & words_ex) / max(len(words_new), len(words_ex))
        if overlap >= threshold:
            return True
    return False


def log(message: str, log_file: Optional[str] = None) -> None:
    line = f"[{datetime.now(timezone.utc).isoformat()}] {message}"
    print(line)
    if log_file:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def main() -> int:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, "config.json")
    if not os.path.exists(config_path):
        print("missing config.json; copy config.example.json to config.json and edit it")
        return 1

    config = load_json(config_path, {})
    token = config.get("telegram_token", "").strip()
    channel = config.get("telegram_channel", "").strip()
    feeds = config.get("feeds", [])
    max_items = int(config.get("max_items_per_feed", 10))
    max_age_hours = int(config.get("max_post_age_hours", 123123))
    exclude_pattern = config.get("exclude_pattern", "")
    state_path = os.path.join(base_dir, config.get("state_file", "state.json"))
    log_file = os.path.join(base_dir, config.get("log_file", "news_bot.log"))

    if not token or not channel or not feeds:
        print("config.json is missing telegram_token, telegram_channel, or feeds")
        return 1

    exclude_re = re.compile(exclude_pattern, re.IGNORECASE) if exclude_pattern else None
    state = load_json(state_path, {"posted": {}})
    posted = state.get("posted", {})

    all_stories: List[Dict[str, str]] = []
    for feed in feeds:
        name = feed["name"]
        url = feed["url"]
        try:
            stories = fetch_rss(url, max_items=max_items)
            for story in stories:
                story["source"] = name
                all_stories.append(story)
            log(f"loaded {len(stories)} stories from {name}", log_file)
        except Exception as e:
            log(f"failed loading {name}: {e}", log_file)

    new_stories: List[Dict[str, str]] = []
    seen_titles: List[str] = [v.get("title", "") for v in posted.values()]

    for story in all_stories:
        title = story["title"]

        # if exclude_re and exclude_re.search(title):
        #     print("skip exclude:", title)
        #     continue
        #
        # if not is_fresh(story.get("pub", ""), max_age_hours):
        #     print("skip stale:", title, "| pub:", story.get("pub", ""))
        #     continue

        # h = story_hash(title)
        # if h in posted:
        #     print("skip posted:", title)
        #     continue

        # if is_near_duplicate(title, seen_titles):
        #     print("skip dup:", title)
        #     continue

        print("keep:", title)
        new_stories.append(story)

    def sort_key(story: Dict[str, str]) -> float:
        dt = parse_date(story.get("pub", ""))
        return dt.timestamp() if dt else time.time()

    new_stories.sort(key=sort_key, reverse=False)
    log(f"posting {len(new_stories)} new stories", log_file)

    posted_now = 0
    for story in new_stories:
        text = build_message(story, story.get("source", "Unknown"))
        image_url = extract_og_image(story["url"])
        ok = post_to_telegram(token, channel, text, image_url=image_url)
        if ok:
            posted_now += 1
            log(f"posted: {story['title']}", log_file)
        else:
            log(f"failed to post: {story['title']}", log_file)
        time.sleep(2)

    state["posted"] = posted
    save_json(state_path, state)
    log(f"done; posted {posted_now} stories", log_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
