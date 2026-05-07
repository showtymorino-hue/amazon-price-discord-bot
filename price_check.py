import json
import os
import re
import sys
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PRODUCT_URL = os.environ.get("AMAZON_PRODUCT_URL", "").strip()
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
STATE_FILE = Path(os.environ.get("PRICE_STATE_FILE", "price_state.json"))


def require_env(name: str, value: str) -> None:
    if not value:
        raise SystemExit(f"Missing environment variable: {name}")


def fetch_page(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
        },
    )
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value)).strip()


def extract_title(html: str) -> str:
    match = re.search(r'id="productTitle"[^>]*>(.*?)</span>', html, re.S)
    if match:
        return compact_text(match.group(1))
    title_match = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    return compact_text(title_match.group(1)) if title_match else "Amazon商品"


def extract_price(html: str) -> str | None:
    patterns = [
        r'class="a-price-whole">([\d,]+)</span>.*?class="a-price-fraction">(\d+)</span>',
        r'class="a-offscreen">(￥[\d,]+)</span>',
        r'"displayPrice"\s*:\s*"(￥[\d,]+)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.S)
        if not match:
            continue
        if len(match.groups()) == 2:
            return f"￥{match.group(1)}"
        return compact_text(match.group(1))
    return None


def load_previous_price() -> str | None:
    if not STATE_FILE.exists():
        return None
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8")).get("price")
    except (OSError, json.JSONDecodeError):
        return None


def save_price(price: str) -> None:
    payload = {
        "price": price,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "url": PRODUCT_URL,
    }
    STATE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def post_discord(content: str) -> None:
    body = json.dumps({"content": content}, ensure_ascii=False).encode("utf-8")
    request = Request(
        WEBHOOK_URL,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        response.read()


def main() -> int:
    require_env("AMAZON_PRODUCT_URL", PRODUCT_URL)
    require_env("DISCORD_WEBHOOK_URL", WEBHOOK_URL)

    try:
        html = fetch_page(PRODUCT_URL)
        title = extract_title(html)
        price = extract_price(html)
        if not price:
            post_discord(f"Amazon価格チェック: 価格を取得できませんでした。\n{PRODUCT_URL}")
            return 2

        previous = load_previous_price()
        if previous and previous != price:
            change = f"前回: {previous} -> 今回: {price}"
        elif previous == price:
            change = f"前回から変化なし: {price}"
        else:
            change = f"初回確認: {price}"

        save_price(price)
        post_discord(f"Amazon価格チェック\n{title}\n{change}\n{PRODUCT_URL}")
        return 0
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        post_discord(f"Amazon価格チェックでエラーが発生しました: {exc}\n{PRODUCT_URL}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
