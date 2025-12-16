import os, json, requests

MAX_CONTENT = 1900  # กันเผื่อ

def mention_text() -> str:
    parts = []
    if os.getenv("MENTION_EVERYONE", "false").lower() == "true":
        parts.append("@everyone")
    mt = os.getenv("MENTION_TARGET", "").strip()
    if mt:
        parts.append(mt)
    return (" ".join(parts) + " ") if parts else ""

def build_message(items):
    rss_url = os.getenv("RSS_URL", "")
    header = f"{mention_text()}พบรายการใหม่ใน RSS"
    if rss_url:
        header += f": {rss_url}"

    lines = []
    for it in items:
        title = (it.get("title") or "").strip() or "(ไม่มีชื่อ)"
        link = (it.get("link") or "").strip()
        when = it.get("published_at") or ""
        line = f"• {title}"
        if when:
            line += f" — {when}"
        if link:
            line += f"\n  {link}"
        lines.append(line)

    content = header + "\n\n" + "\n\n".join(lines)
    # จำกัดความยาวไม่ให้เกิน 2000 ตัวอักษร
    if len(content) > MAX_CONTENT:
        content = content[:MAX_CONTENT] + "\n… (ตัดข้อความเพื่อไม่ให้เกินลิมิต)"
    return content

def send_discord(items):
    url = os.getenv("DISCORD_WEBHOOK_URL")
    if not url:
        raise RuntimeError("DISCORD_WEBHOOK_URL not set")

    content = build_message(items).strip()
    if not content:
        raise RuntimeError("Empty content for Discord")

    resp = requests.post(url, json={"content": content}, timeout=20)
    if not resp.ok:
        # โชว์ข้อความผิดพลาดจาก Discord เพื่อดีบั๊ก
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
    send_discord(items)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
