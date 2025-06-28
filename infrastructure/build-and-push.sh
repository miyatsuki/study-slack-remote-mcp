#!/bin/bash

# Docker イメージをビルドしてECRにプッシュするスクリプト

set -e

# 引数処理
ENV_NAME="${1:-dev}"
AWS_ACCOUNT_ID="${2:-$(aws sts get-caller-identity --query Account --output text)}"
AWS_REGION="${3:-$(aws configure get region || echo 'ap-northeast-1')}"

# 変数設定
ECR_REPOSITORY="slack-mcp-server-${ENV_NAME}"
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}"
IMAGE_TAG="latest"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "🐳 Docker イメージをビルド・プッシュします"
echo "   プロジェクト: $PROJECT_ROOT"
echo "   ECRリポジトリ: $ECR_URI"
echo "   イメージタグ: $IMAGE_TAG"
echo "   環境: $ENV_NAME"
echo "   リージョン: $AWS_REGION"
echo ""

# ECR ログイン
echo "🔐 ECR にログイン中..."
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

# Dockerイメージをビルド
echo "🔨 Docker イメージをビルド中..."
docker build -t "$ECR_REPOSITORY:$IMAGE_TAG" "$PROJECT_ROOT"

# イメージにECRタグを付与
echo "🏷️  ECR タグを付与中..."
docker tag "$ECR_REPOSITORY:$IMAGE_TAG" "$ECR_URI:$IMAGE_TAG"

# ECRにプッシュ
echo "📤 ECR にプッシュ中..."
docker push "$ECR_URI:$IMAGE_TAG"

# App Runnerサービスを更新するには、再度CDKデプロイを実行する必要があります
echo ""
echo "✅ イメージのプッシュが完了しました!"
echo "   イメージURI: $ECR_URI:$IMAGE_TAG"
echo ""
echo "📝 次のステップ:"
echo "   1. CDKを使用してApp Runnerを更新:"
echo "      cd $PROJECT_ROOT/infrastructure"
echo "      ./deploy.sh $ENV_NAME"
echo ""
echo "   2. App Runnerのデプロイ状況を確認:"
echo "      AWS Console > App Runner > slack-mcp-server-$ENV_NAME"