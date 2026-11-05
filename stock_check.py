import json
import os
import re
import sys
from datetime import datetime
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


PRODUCT_URL = os.environ.get("STOCK_PRODUCT_URL", "").strip()
PRODUCT_NAME = os.environ.get("STOCK_PRODUCT_NAME", "商品").strip()
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
NOTIFICATION_LABEL = os.environ.get("STOCK_NOTIFICATION_LABEL", "").strip()
TOKYO = ZoneInfo("Asia/Tokyo")


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
        charset = response.headers.get_content_charset() or "euc-jp"
        return response.read().decode(charset, errors="replace")


def compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value)).strip()


def extract_title(html: str) -> str:
    patterns = [
        r'<h1[^>]*class="[^"]*item-name[^"]*"[^>]*>(.*?)</h1>',
        r"<title>(.*?)</title>",
        r'"name"\s*:\s*"((?:\\.|[^"])*)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.S | re.I)
        if match:
            title = match.group(1)
            try:
                title = json.loads(f'"{title}"')
            except json.JSONDecodeError:
                pass
            return compact_text(title.replace(" - ROY reflect overjoy", ""))
    return PRODUCT_NAME


def extract_stock_count(html: str) -> int | None:
    match = re.search(r'"stock_num"\s*:\s*(-?\d+)', html)
    if match:
        return int(match.group(1))
    return None


def is_available(html: str) -> bool:
    stock_count = extract_stock_count(html)
    if stock_count is not None:
        return stock_count > 0

    sold_out_signals = [
        "SOLD OUT",
        "在庫なし",
        'class="soldout"',
        'class="stock_zero"',
    ]
    upper_html = html.upper()
    if any(signal.upper() in upper_html for signal in sold_out_signals):
        return False

    purchase_signals = [
        "カートに入れる",
        "cart.js",
        "async_cart_in",
    ]
    return any(signal in html for signal in purchase_signals)


def post_discord(content: str) -> None:
    body = json.dumps({"content": content}, ensure_ascii=False).encode("utf-8")
    request = Request(
        WEBHOOK_URL,
        data=body,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "amazon-price-discord-bot/1.0",
        },
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        response.read()


def build_message(title: str, available: bool, checked_at: datetime) -> str:
    status = "在庫あり／購入可能" if available else "在庫なし／SOLD OUT"
    heading = "ROY在庫チェック"
    if NOTIFICATION_LABEL:
        heading = f"{NOTIFICATION_LABEL}: {heading}"
    return (
        f"{heading}\n"
        f"商品名: {title or PRODUCT_NAME}\n"
        f"在庫状況: {status}\n"
        f"確認日時: {checked_at.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
        f"商品URL: {PRODUCT_URL}"
    )


def main() -> int:
    require_env("STOCK_PRODUCT_URL", PRODUCT_URL)
    require_env("DISCORD_WEBHOOK_URL", WEBHOOK_URL)

    try:
        html = fetch_page(PRODUCT_URL)
        title = extract_title(html)
        available = is_available(html)
        checked_at = datetime.now(TOKYO)
        post_discord(build_message(title, available, checked_at))
        return 0
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        checked_at = datetime.now(TOKYO)
        label = f"{NOTIFICATION_LABEL}: " if NOTIFICATION_LABEL else ""
        post_discord(
            f"{label}ROY在庫チェックでエラーが発生しました: {exc}\n"
            f"商品名: {PRODUCT_NAME}\n"
            f"確認日時: {checked_at.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
            f"商品URL: {PRODUCT_URL}"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
