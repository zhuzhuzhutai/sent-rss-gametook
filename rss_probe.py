import os, sys, json, time, calendar, hashlib
from datetime import datetime, timezone, timedelta

import aiohttp
import feedparser
from dotenv import load_dotenv

load_dotenv()
RSS_URL = os.getenv("RSS_URL")

SEEN_FILE = "seen.json"
STATE_FILE = "feed_state.json"
NEW_FILE = "new_items.json"

def load_seen() -> set[str]:
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data if isinstance(data, list) else [])
        except Exception:
            return set()
    return set()

def save_seen(seen: set[str]) -> None:
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, indent=2, ensure_ascii=False)

def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def fingerprint(entry) -> str:
    base = (getattr(entry, "id", "") or "") + \
           (getattr(entry, "link", "") or "") + \
           (getattr(entry, "title", "") or "")
    return hashlib.sha1(base.encode("utf-8", errors="ignore")).hexdigest()

def entry_timestamp(e) -> float:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        t = getattr(e, key, None)
        if t:
            return calendar.timegm(t)  # feedparser ให้เป็น UTC
    return time.time()

def entry_to_dict(e, ts: float, fp: str) -> dict:
    thai = timezone(timedelta(hours=7))
    # เก็บ raw summary ไว้เผื่อ notify จะไป strip HTML เอง
    summary = getattr(e, "summary", "") or ""
    return {
        "fingerprint": fp,
        "title": getattr(e, "title", "") or "",
        "link": getattr(e, "link", "") or "",
        "summary": summary,
        "published_ts": ts,
        "published_at": datetime.fromtimestamp(ts, tz=thai).isoformat(),
        # แนบฟิลด์เสริมเผื่อบางฟีด
        "media_thumbnail": getattr(e, "media_thumbnail", None),
        "media_content": getattr(e, "media_content", None),
        "enclosures": getattr(e, "enclosures", None),
        "description": getattr(e, "description", None),
        "content": getattr(e, "content", None),
    }

async def main() -> int:
    if not RSS_URL:
        print("RSS_URL not set in .env", file=sys.stderr)
        return 1

    seen = load_seen()
    state = load_state()
    etag = state.get("etag")
    last_mod = state.get("last_modified")

    headers = {"User-Agent": "Mozilla/5.0 (RSS Probe)"}
    if etag:
        headers["If-None-Match"] = etag
    if last_mod:
        headers["If-Modified-Since"] = last_mod

    raw = None
    async with aiohttp.ClientSession() as session:
        async with session.get(RSS_URL, headers=headers, timeout=25) as resp:
            if resp.status == 304:
                thai = timezone(timedelta(hours=7))
                state["checked_at"] = datetime.now(timezone.utc).astimezone(thai).isoformat()
                save_state(state)
                if os.path.exists(NEW_FILE):
                    os.remove(NEW_FILE)
                return 1
            resp.raise_for_status()
            raw = await resp.read()
            if resp.headers.get("ETag"):
                state["etag"] = resp.headers["ETag"]
            if resp.headers.get("Last-Modified"):
                state["last_modified"] = resp.headers["Last-Modified"]

    feed = feedparser.parse(raw)
    thai_tz = timezone(timedelta(hours=7))
    state["checked_at"] = datetime.now(timezone.utc).astimezone(thai_tz).isoformat()

    if not getattr(feed, "entries", None):
        save_state(state)
        if os.path.exists(NEW_FILE):
            os.remove(NEW_FILE)
        return 1

    items = []
    for e in feed.entries:
        ts = entry_timestamp(e)
        fp = fingerprint(e)
        items.append((ts, e, fp))

    # เลือกบนสุด 10 กันตกหล่น ปรับได้ตามถี่ของฟีด
    items.sort(key=lambda x: x[0], reverse=True)
    topN = items[:10]
    if topN:
        latest_ts = topN[0][0]
        state["last_pubdate"] = datetime.fromtimestamp(latest_ts, tz=thai_tz).isoformat()

    new_entries = []
    for ts, e, fp in topN:
        if fp not in seen:
            new_entries.append(entry_to_dict(e, ts, fp))

    save_state(state)

    if not new_entries:
        if os.path.exists(NEW_FILE):
            os.remove(NEW_FILE)
        return 1

    # เขียนรายการใหม่ทั้งหมด
    with open(NEW_FILE, "w", encoding="utf-8") as f:
        json.dump(new_entries, f, indent=2, ensure_ascii=False)

    # มาร์คว่าเห็นแล้วทั้งหมด เพื่อกันส่งซ้ำรอบหน้า
    for it in new_entries:
        seen.add(it["fingerprint"])
    save_seen(seen)
    return 0

if __name__ == "__main__":
    import asyncio
    code = asyncio.run(main())
    sys.exit(code)
