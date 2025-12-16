import os, json, re, html, time, requests

MAX_LINE = 300  # จำกัดความยาวคำอธิบายต่อรายการ
TAG_RE = re.compile(r"<[^>]+>")

def strip_html(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r"<\s*(br|/p)\s*>", "\n", s, flags=re.IGNORECASE)
    s = TAG_RE.sub("", s)
    s = html.unescape(s)
    s = re.sub(r"\s+\n", "\n", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s.strip()

def build_single_message(it: dict) -> str:
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

    parts = []
    mention = os.getenv("MENTION_TARGET", "").strip()
    if os.getenv("MENTION_EVERYONE", "false").lower() == "true":
        mention = ("@everyone " + mention).strip()
    if mention:
        parts.append(mention)

    line = f"• {title}"
    if link:
        line += f"\n  {link}"
    if text:
        line += f"\n  {text}"
    parts.append(line)

    content = "\n".join(parts).strip()
    if len(content) > 1900:
        content = content[:1900] + "\n…"
    return content

def send_message(content: str):
    url = os.getenv("DISCORD_WEBHOOK_URL")
    if not url:
        raise RuntimeError("DISCORD_WEBHOOK_URL not set")
    resp = requests.post(url, json={"content": content}, timeout=25)
    if not resp.ok:
        raise requests.HTTPError(f"{resp.status_code} {resp.reason}: {resp.text}", response=resp)

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

    for idx, it in enumerate(items, 1):
        content = build_single_message(it)
        send_message(content)
        print(f"Sent {idx}/{len(items)}")
        time.sleep(1)  # หน่วงเล็กน้อยกัน rate limit

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
