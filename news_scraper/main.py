#!/usr/bin/env python3
import hashlib
import json
import os
import re
import time
import urllib.request
import xml.etree.ElementTree as XmlElementTree
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional

def log(message: str, log_file: Optional[str] = None) -> None:
    line = f"[{datetime.now(timezone.utc).isoformat()}] {message}"
    print(line)
    if log_file:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")

def get_latest_chrome_user_agent() -> str:
    default_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.7727.57 Safari/537.36"
    try:
        request = urllib.request.Request(
            "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions.json",
            headers={"User-Agent": default_ua}
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            version = data["channels"]["Stable"]["version"]
            return f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{version} Safari/537.36"
    except Exception:
        log("Failed to fetch the latest version of Chrome for User-Agent, fallback to defaults", "news.log")
        return default_ua

USER_AGENT = get_latest_chrome_user_agent()

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


class HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_parts = []

    def handle_data(self, data: str) -> None:
        self.text_parts.append(data)


def strip_html(text: str) -> str:
    if not text:
        return ""
    parser = HTMLTextExtractor()
    parser.feed(unescape(text))
    return "".join(parser.text_parts).strip()


def fetch_rss(url: str, max_items: int = 10) -> List[Dict[str, str]]:
    stories: List[Dict[str, str]] = []
    raw = fetch_url(url)
    root = XmlElementTree.fromstring(raw)

    def add_story(title: str, link: str, desc: str, pub: str) -> None:
        if title and link:
            stories.append(
                {
                    "title": unescape(title),
                    "url": link,
                    "desc": strip_html(desc)[:200],
                    "pub": pub,
                }
            )

    items = root.findall(".//item")
    if items:
        for item in items[:max_items]:
            add_story(
                (item.findtext("title", "") or "").strip(),
                (item.findtext("link", "") or "").strip(),
                (item.findtext("description", "") or "").strip(),
                (
                    item.findtext("pubDate", "") or item.findtext("published", "") or ""
                ).strip(),
            )
    else:
        atom = "{http://www.w3.org/2005/Atom}"
        for entry in root.findall(f".//{atom}entry")[:max_items]:
            link_el = entry.find(f"{atom}link")
            add_story(
                (entry.findtext(f"{atom}title", "") or "").strip(),
                (link_el.attrib.get("href", "") if link_el is not None else "").strip(),
                (entry.findtext(f"{atom}summary", "") or "").strip(),
                (entry.findtext(f"{atom}updated", "") or "").strip(),
            )

    return stories


def story_hash(title: str) -> str:
    clean = "".join(c for c in title.lower().strip() if c.isalnum() or c == " ")
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


class OpenGraphParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.image_url = None

    def handle_starttag(self, tag: str, attrs: List[tuple[str, Optional[str]]]) -> None:
        if self.image_url or tag != "meta":
            return

        attrs_dict = dict(attrs)
        prop = attrs_dict.get("property") or attrs_dict.get("name")

        if prop in ("og:image", "twitter:image"):
            self.image_url = attrs_dict.get("content")


def extract_og_image(url: str) -> Optional[str]:
    try:
        html = fetch_url(url, timeout=8)[:120000].decode("utf-8", errors="ignore")
        parser = OpenGraphParser()
        parser.feed(html)
        return parser.image_url
    except Exception:
        return None


def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


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


def telegram_request(
    token: str, method: str, payload: Dict[str, Any]
) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    url = f"https://api.telegram.org/bot{token}/{method}"
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def post_to_telegram(
    token: str, channel: str, text: str, image_url: Optional[str] = None
) -> bool:
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
                resp = telegram_request(
                    token,
                    "sendMessage",
                    {
                        "chat_id": channel,
                        "text": text[:4096],
                        "parse_mode": "HTML",
                        "disable_web_page_preview": False,
                    },
                )
                return bool(resp.get("ok", False))
            except Exception:
                return False
        return False


def is_near_duplicate(
    new_title: str, existing_titles: List[str], threshold: float = 0.7
) -> bool:
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




def main() -> int:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, "config.json")
    if not os.path.exists(config_path):
        print(
            "missing config.json; copy config.example.json to config.json and edit it"
        )
        return 1

    config = load_json(config_path, {})
    token = config.get("telegram_token", "").strip()
    channel = config.get("telegram_channel", "").strip()
    feeds = config.get("feeds", [])
    max_items = int(config.get("max_items_per_feed", 10))
    # max_age_hours = int(config.get("max_post_age_hours", 123123))
    # exclude_pattern = config.get("exclude_pattern", "")
    state_path = os.path.join(base_dir, config.get("state_file", "state.json"))
    log_file = os.path.join(base_dir, config.get("log_file", "news.log"))

    if not token or not channel or not feeds:
        print("config.json is missing telegram_token, telegram_channel, or feeds")
        return 1

    # exclude_re = re.compile(exclude_pattern, re.IGNORECASE) if exclude_pattern else None
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
    # seen_titles: List[str] = [v.get("title", "") for v in posted.values()]

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
