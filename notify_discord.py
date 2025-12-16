import os, json, re, html, requests
from datetime import datetime, timezone, timedelta

MAX_DESC = 380  # ความยาวคำอธิบายต่อการ์ด
BATCH_SIZE = 10 # Discord จำกัด embeds ต่อข้อความไม่เกิน 10

IMG_TAG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)

def thai_iso(ts_str: str | None) -> str | None:
    # ts_str รูปแบบ ISO จาก rss_probe.py อยู่ใน Asia/Bangkok อยู่แล้ว ใช้ตรงๆได้
    return ts_str or None

def extract_image(it: dict) -> str | None:
    # 1) ฟิลด์ที่มักมีจาก feedparser
    for key in ("media_thumbnail", "media_content"):
        v = it.get(key)
        if isinstance(v, list) and v:
            url = v[0].get("url")
            if url: return url
        if isinstance(v, dict):
            url = v.get("url")
            if url: return url
    # 2) enclosure (บางฟีดใส่ภาพเป็น enclosure type=image/*)
    encl = it.get("enclosures") or it.get("enclosure")
    if isinstance(encl, list) and encl:
        for e in encl:
            if isinstance(e, dict) and str(e.get("type","")).startswith("image/"):
                if e.get("href"): return e["href"]
                if e.get("url"):  return e["url"]
    elif isinstance(encl, dict):
        if str(encl.get("type","")).startswith("image/"):
            return encl.get("href") or encl.get("url")

    # 3) summary/detail ที่มี <img src="...">
    for key in ("summary", "summary_detail", "content", "description"):
        v = it.get(key)
        if isinstance(v, dict):
            v = v.get("value")
        if isinstance(v, list) and v:
            # content เป็น list ของบล็อก HTML
            for c in v:
                if isinstance(c, dict):
                    html_text = c.get("value") or ""
                else:
                    html_text = str(c)
                m = IMG_TAG_RE.search(html_text or "")
                if m:
                    return m.group(1)
        elif isinstance(v, str):
            m = IMG_TAG_RE.search(v)
            if m:
                return m.group(1)

    # 4) เผื่อมีฟิลด์ image โดยตรง
    if isinstance(it.get("image"), dict):
        url = it["image"].get("href") or it["image"].get("url")
        if url: return url

    return None

def safe_trim(text: str, limit: int) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[:limit-1] + "…"

def build_embeds(items: list[dict]) -> list[dict]:
    embeds = []
    for it in items:
        title = it.get("title") or "(ไม่มีชื่อ)"
        url = it.get("link") or None
        desc_raw = it.get("summary") or ""
        description = safe_trim(desc_raw, MAX_DESC) if desc_raw else None
        ts = thai_iso(it.get("published_at"))
        img = extract_image(it)

        embed = {
            "title": safe_trim(title, 240),
            "url": url,
            "description": description,
            "timestamp": ts,
            "color": 0x5865F2,  # Blurple
        }
        if img:
            embed["image"] = {"url": img}

        # ลบคีย์ที่เป็น None เพื่อไม่ให้ payload เกะกะ
        embed = {k: v for k, v in embed.items() if v is not None}
        embeds.append(embed)
    return embeds

def post_discord(embeds_batch: list[dict]) -> None:
    url = os.getenv("DISCORD_WEBHOOK_URL")
    if not url:
        raise RuntimeError("DISCORD_WEBHOOK_URL not set")
    rss_url = os.getenv("RSS_URL", "")
    header = f"พบรายการใหม่ใน RSS: {rss_url}" if rss_url else "พบรายการใหม่ใน RSS"
    payload = {
        "content": header,
        "embeds": embeds_batch,
        "allowed_mentions": {
            "parse": ["everyone", "roles", "users"] if os.getenv("MENTION_EVERYONE","false").lower()=="true" else [],
        },
    }
    mention_target = os.getenv("MENTION_TARGET", "").strip()
    if mention_target:
        payload["content"] = f"{mention_target} " + payload["content"]

    r = requests.post(url, json=payload, timeout=25)
    if not r.ok:
        raise requests.HTTPError(f"{r.status_code} {r.reason}: {r.text}", response=r)

def main():
    path = "new_items.json"
    if not os.path.exists(path):
        print("No new_items.json; nothing to notify.")
        return 0
    with open(path, "r", encoding="utf-8") as f:
        items = json.load(f)
    if not items:
        print("Empty new items.")
        return 0

    embeds = build_embeds(items)
    # ส่งเป็นชุด ชุดละไม่เกิน 10 embeds
    for i in range(0, len(embeds), BATCH_SIZE):
        batch = embeds[i:i+BATCH_SIZE]
        post_discord(batch)
    print(f"Sent {len(embeds)} embed(s) to Discord.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
