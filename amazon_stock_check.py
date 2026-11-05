import json
import os
import re
import sys
from datetime import datetime
from html import unescape
from urllib.request import Request, urlopen


PRODUCT_URL = os.environ.get("AMAZON_STOCK_PRODUCT_URL", "").strip()
PRODUCT_NAME = os.environ.get("AMAZON_STOCK_PRODUCT_NAME", "Amazon商品").strip()
TARGET_COLOR = os.environ.get("AMAZON_STOCK_COLOR", "").strip()
TARGET_SELLER = os.environ.get("AMAZON_STOCK_SELLER", "").strip()
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()


def compact(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value)).strip()


def fetch_page(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36",
            "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8",
        },
    )
    with urlopen(request, timeout=30) as response:
        return response.read().decode(response.headers.get_content_charset() or "utf-8", errors="replace")


def page_text(html: str) -> str:
    return compact(re.sub(r"<[^>]+>", " ", html))


def extract_title(html: str) -> str:
    match = re.search(r'<span[^>]+id="productTitle"[^>]*>(.*?)</span>', html, re.S | re.I)
    if match:
        return compact(match.group(1))
    match = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    return compact(match.group(1)) if match else PRODUCT_NAME


def extract_availability(html: str) -> str:
    text = page_text(html)
    if re.search(r"在庫あり|通常[、,]?\s*在庫あり|お急ぎ便", text):
        return "在庫あり"
    if re.search(r"在庫切れ|一時的に在庫切れ|現在お取り扱いできません|SOLD OUT", text, re.I):
        return "在庫なし"
    return "在庫状況不明"


def extract_merchant(html: str) -> str:
    match = re.search(r"offer-display-feature-name=\"desktop-merchant-info\".*?offer-display-feature-text-message[^>]*>(.*?)</(?:a|span)>", html, re.S | re.I)
    return compact(match.group(1)) if match else "不明"


def extract_asin(html: str) -> str:
    match = re.search(r'<input[^>]+id="ASIN"[^>]+value="([A-Z0-9]+)"', html, re.I)
    return match.group(1) if match else "不明"


def main() -> int:
    for name, value in {
        "AMAZON_STOCK_PRODUCT_URL": PRODUCT_URL,
        "DISCORD_WEBHOOK_URL": WEBHOOK_URL,
    }.items():
        if not value:
            raise SystemExit(f"Missing environment variable: {name}")

    checked_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    try:
        html = fetch_page(PRODUCT_URL)
        title = extract_title(html)
        availability = extract_availability(html)
        merchant = extract_merchant(html)
        asin = extract_asin(html)
        color_ok = not TARGET_COLOR or TARGET_COLOR.lower() in title.lower() or TARGET_COLOR.lower() in page_text(html).lower()
        seller_ok = not TARGET_SELLER or TARGET_SELLER.lower() in merchant.lower()
        amazon_fulfilled = bool(re.search(r"Amazon.co.jp|Amazonから発送|アマゾン配送", page_text(html), re.I))
        conditions_ok = availability == "在庫あり" and color_ok and seller_ok and amazon_fulfilled
        status = "入荷あり（購入条件一致）" if conditions_ok else "対象条件での販売なし"
        message = (
            f"Amazon入荷チェック\n{PRODUCT_NAME}\n"
            f"判定: {status}\n在庫: {availability}\n色: {TARGET_COLOR or '指定なし'} ({'一致' if color_ok else '不一致'})\n"
            f"販売元: {merchant} ({'一致' if seller_ok else '不一致'})\n"
            f"Amazon発送条件: {'確認' if amazon_fulfilled else '不一致/確認不可'}\n"
            f"確認日時: {checked_at}\nASIN: {asin}\n{PRODUCT_URL}"
        )
    except Exception as exc:
        message = f"Amazon入荷チェックでエラーが発生しました\n{PRODUCT_NAME}\n確認日時: {checked_at}\n{exc}\n{PRODUCT_URL}"
        conditions_ok = False

    body = json.dumps({"content": message}, ensure_ascii=False).encode("utf-8")
    request = Request(WEBHOOK_URL, data=body, headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "amazon-price-discord-bot/1.0"}, method="POST")
    with urlopen(request, timeout=30) as response:
        response.read()
    return 0


if __name__ == "__main__":
    sys.exit(main())
