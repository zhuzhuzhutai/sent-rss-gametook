import os, json, re, html, requests

MAX_DESC = 220   # คำอธิบายสั้น กระชับ
BATCH_SIZE = 10  # Discord จำกัด embeds ต่อข้อความ

IMG_TAG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")  # ลบแท็กทั้งหมด

def strip_html(text: str) -> str:
    if not text:
        return ""
    # แทน br/p ด้วยขึ้นบรรทัด ก่อนลบแท็กอื่น
    text = re.sub(r"<\s*(br|/p)\s*>", "\n", text, flags=re.IGNORECASE)
    text = TAG_RE.sub("", text)              # ลบแท็ก
    text = html.unescape(text)               # แปลง entity
    text = re.sub(r"\s+\n", "\n", text)      # เก็บบรรทัดโล่งให้น้อยลง
    text = re.sub(r"[ \t]{2,}", " ", text)   # ช่องว่างซ้ำ
    return text.strip()

def safe(text: str, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit-1] + "…"

def extract_image_from_html(s: str | None) -> str | None:
    if not s:
        return None
    m = IMG_TAG_RE.search(s)
    return m.group(1) if m else None

def pick_image(it: dict) -> str | None:
    # media_thumbnail/media_content
    for k in ("media_thumbnail", "media_content"):
        v = it.get(k)
        if isinstance(v, list) and v:
            url = v[0].get("url")
            if url: return url
        if isinstance(v, dict):
            url = v.get("url")
            if url: return url
    # enclosure(s)
    enc = it.get("enclosures") or it.get("enclosure")
    if isinstance(enc, list):
        for e in enc:
            if isinstance(e, dict) and str(e.get("type","")).startswith("image/"):
                return e.get("href") or e.get("url")
    elif isinstance(enc, dict):
        if str(enc.get("type","")).startswith("image/"):
            return enc.get("href") or enc.get("url")
    # จาก summary/content ที่มี <img>
    for k in ("summary", "description", "content"):
        v = it.get(k)
        if isinstance(v, list) and v:
            for c in v:
                html_text = c.get("value") if isinstance(c, dict) else str(c)
                url = extract_image_from_html(html_text)
                if url: return url
        elif isinstance(v, dict):
            url = extract_image_from_html(v.get("value"))
            if url: return url
        elif isinstance(v, str):
            url = extract_image_from_html(v)
            if url: return url
    return None

def build_embeds(items: list[dict]) -> list[dict]:
    embeds = []
    for it in items:
        title = safe(it.get("title") or "(ไม่มีชื่อ)", 240)
        url = it.get("link") or None
        # ใช้ summary/description/content เป็นข้อความล้วน
        raw = it.get("summary") or it.get("description") or ""
        if isinstance(raw, list):  # บางฟีดให้ list ของบล็อก HTML
            raw = raw[0].get("value") if raw and isinstance(raw[0], dict) else str(raw[0])
        elif isinstance(raw, dict):
            raw = raw.get("value") or ""
        description = safe(strip_html(raw), MAX_DESC) or None
        ts = it.get("published_at") or None
        img = pick_image(it)

        embed = {
            "title": title,
            "url": url,
            "description": description,
            "timestamp": ts,
            "color": 0x2ECC71,  # เขียวอ่อนอ่านง่าย
        }
        if img:
            embed["image"] = {"url": img}
        # ลบ None
        embeds.append({k: v for k, v in embed.items() if v is not None})
    return embeds

def post_batch(embeds_batch: list[dict]) -> None:
    url = os.getenv("DISCORD_WEBHOOK_URL")
    if not url:
        raise RuntimeError("DISCORD_WEBHOOK_URL not set")
    rss_url = os.getenv("RSS_URL", "")
    content = f"พบรายการใหม่ใน RSS: {rss_url}" if rss_url else "พบรายการใหม่ใน RSS"
    mention = os.getenv("MENTION_TARGET", "").strip()
    if os.getenv("MENTION_EVERYONE","false").lower() == "true":
        mention = ("@everyone " + mention).strip()
    if mention:
        content = f"{mention} {content}"

    payload = {"content": content, "embeds": embeds_batch}
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
    for i in range(0, len(embeds), BATCH_SIZE):
        post_batch(embeds[i:i+BATCH_SIZE])
    print(f"Sent {len(embeds)} embeds.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
