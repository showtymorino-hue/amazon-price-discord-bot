# amazon-price-discord-bot

Amazon.co.jpの商品価格を確認して、Discord Webhookへ通知するローカル実行用スクリプトです。

## 使う環境変数

秘密情報はGitHubに保存しません。実行するPC側で環境変数として設定します。

- `AMAZON_PRODUCT_URL`: 価格を確認するAmazon商品URL
- `DISCORD_WEBHOOK_URL`: DiscordチャンネルのWebhook URL
- `PRICE_STATE_FILE`: 前回価格を保存するJSONファイルのパス、省略時は `price_state.json`

## 手動実行

```powershell
$env:AMAZON_PRODUCT_URL = "https://www.amazon.co.jp/dp/B0D4TSGKPY/"
$env:DISCORD_WEBHOOK_URL = "DiscordのWebhook URL"
python .\price_check.py
```

## 運用メモ

- Discord Webhook URLはパスワードに近い秘密情報です。GitHubには保存しません。
- PCが起動していない時間の実行はスキップされます。
- Amazonページ構造の変更やアクセス制限により、価格が取得できない場合があります。
