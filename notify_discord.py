import os, json, re, html, requests

MAX_LINE = 300  # จำกัดความยาวคำอธิบายต่อรายการ
TAG_RE = re.compile(r"<[^>]+>")
IMG_TAG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)

def strip_html(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r"<\s*(br|/p)\s*>", "\n", s, flags=re.IGNORECASE)
    s = TAG_RE.sub("", s)
    s = html.unescape(s)
    s = re.sub(r"\s+\n", "\n", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s.strip()

def first_image_url(s: str | None) -> str | None:
    if not s:
        return None
    m = IMG_TAG_RE.search(s)
    return m.group(1) if m else None

def build_message(items):
    parts = []
    mention = os.getenv("MENTION_TARGET", "").strip()
    if os.getenv("MENTION_EVERYONE", "false").lower() == "true":
        mention = ("@everyone " + mention).strip()
    if mention:
        parts.append(mention)

    for it in items:
        title = (it.get("title") or "(ไม่มีชื่อ)").strip()
        link = (it.get("link") or "").strip()
        raw = it.get("summary") or it.get("description") or ""
        if isinstance(raw, dict):
            raw = raw.get("value") or ""
        if isinstance(raw, list) and raw:
            raw = raw[0].get("value") if isinstance(raw[0], dict) else str(raw[0])
        text = strip_html(raw)
        if len(text) > MAX_LINE:
            text = text[:MAX_LINE-1] + "…"

        line = f"• {title}"
        if link:
            line += f"\n  {link}"
        if text:
            line += f"\n  {text}"

        # ถ้าอยากแสดงลิงก์รูป (ไม่ embed) ให้เปิดสองบรรทัดข้างล่างนี้
        # img = first_image_url(raw)
        # if img: line += f"\n  [image] {img}"

        parts.append(line)
        parts.append("")  # เว้นบรรทัด

    content = "\n".join(parts).strip()
    if len(content) > 1900:  # กันลิมิต 2000 ตัวอักษร
        content = content[:1900] + "\n…"
    return content

def main():
    url = os.getenv("DISCORD_WEBHOOK_URL")
    if not url:
        raise RuntimeError("DISCORD_WEBHOOK_URL not set")

    path = "new_items.json"
    if not os.path.exists(path):
        print("No new_items.json; nothing to notify.")
        return 0

    with open(path, "r", encoding="utf-8") as f:
        items = json.load(f)
    if not items:
        print("Empty new items.")
        return 0

    content = build_message(items)
    resp = requests.post(url, json={"content": content}, timeout=25)
    print("Discord status:", resp.status_code, resp.text[:200])
    resp.raise_for_status()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
