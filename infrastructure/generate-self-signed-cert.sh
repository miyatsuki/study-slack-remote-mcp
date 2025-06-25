#!/bin/bash

# 自己署名証明書を生成してACMにインポートするスクリプト

set -e

# 変数設定
CERT_DIR="./certs"
PRIVATE_KEY="$CERT_DIR/private.key"
CERTIFICATE="$CERT_DIR/certificate.crt"
REGION="${AWS_REGION:-ap-northeast-1}"
ENV_NAME="${ENV_NAME:-dev}"

# 証明書ディレクトリを作成
mkdir -p "$CERT_DIR"

echo "🔐 自己署名証明書を生成中..."

# 秘密鍵を生成
openssl genrsa -out "$PRIVATE_KEY" 2048

# ALB DNS名を取得（引数で指定可能）
ALB_DNS_NAME="${1:-slack-mcp.example.com}"

# CNの長さが64文字を超えないように短縮
if [ ${#ALB_DNS_NAME} -gt 64 ]; then
    # 長い場合は短縮版を使用
    CN_NAME="slack-mcp-${ENV_NAME}.elb.amazonaws.com"
else
    CN_NAME="$ALB_DNS_NAME"
fi

# 自己署名証明書を生成（ALBのDNS名を使用）
openssl req -new -x509 -key "$PRIVATE_KEY" -out "$CERTIFICATE" -days 365 -subj "/C=US/ST=State/L=City/O=SlackMCP/CN=$CN_NAME"

echo "✅ 証明書を生成しました:"
echo "   秘密鍵: $PRIVATE_KEY"
echo "   証明書: $CERTIFICATE"

# ACMに証明書をインポート
echo "📤 ACMに証明書をインポート中..."

CERT_ARN=$(aws acm import-certificate \
  --certificate "fileb://$CERTIFICATE" \
  --private-key "fileb://$PRIVATE_KEY" \
  --region "$REGION" \
  --query 'CertificateArn' \
  --output text)

echo "✅ 証明書をACMにインポートしました:"
echo "   ARN: $CERT_ARN"

# Parameter Storeに証明書ARNを保存
echo "💾 Parameter Storeに証明書ARNを保存中..."

aws ssm put-parameter \
  --name "/slack-mcp/$ENV_NAME/certificate-arn" \
  --value "$CERT_ARN" \
  --type "String" \
  --overwrite \
  --region "$REGION"

echo "✅ Parameter Storeに保存しました: /slack-mcp/$ENV_NAME/certificate-arn"

# 証明書ファイルを削除（セキュリティのため）
rm -f "$PRIVATE_KEY" "$CERTIFICATE"
rmdir "$CERT_DIR" 2>/dev/null || true

echo ""
echo "🎉 完了! 以下のいずれかの方法でCDKデプロイ時に証明書を使用できます:"
echo ""
echo "方法1: 環境変数を使用"
echo "  export CERTIFICATE_ARN='$CERT_ARN'"
echo "  cd infrastructure && cdk deploy SlackMcpStack-$ENV_NAME"
echo ""
echo "方法2: CDKコンテキストを使用"
echo "  cd infrastructure && cdk deploy SlackMcpStack-$ENV_NAME --context certificateArn='$CERT_ARN'"
echo ""
echo "方法3: Parameter Storeから自動読み込み（要CDK修正）"
echo ""
echo "⚠️  注意: この証明書は自己署名証明書のため、ブラウザで警告が表示されます。"
echo "   本番環境では独自ドメインとACM証明書の使用を推奨します。"