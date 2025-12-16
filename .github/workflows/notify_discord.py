import os, json, requests

def mention_text() -> str:
    parts = []
    if os.getenv("MENTION_EVERYONE", "false").lower() == "true":
        parts.append("@everyone")
    mt = os.getenv("MENTION_TARGET", "").strip()
    if mt:
        parts.append(mt)
    return (" ".join(parts) + " ") if parts else ""

def send_discord(items):
    url = os.getenv("DISCORD_WEBHOOK_URL")
    if not url:
        raise RuntimeError("DISCORD_WEBHOOK_URL not set")

    rss_url = os.getenv("RSS_URL", "")
    header = f"{mention_text()}พบรายการใหม่ใน RSS"
    if rss_url:
        header += f": {rss_url}"

    lines = []
    for it in items:
        title = it.get("title", "").strip() or "(ไม่มีชื่อ)"
        link = it.get("link", "").strip()
        when = it.get("published_at", "")
        line = f"• {title} — {when}"
        if link:
            line += f"\n  {link}"
        lines.append(line)

    content = header + "\n\n" + "\n\n".join(lines)
    resp = requests.post(url, json={"content": content}, timeout=20)
    resp.raise_for_status()

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