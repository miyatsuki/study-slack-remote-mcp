#!/bin/bash

# Slack MCP Server Main Infrastructure Deployment Script - App Runner Version
# Prerequisites must be deployed first using deploy-prerequisites.sh

set -e

# Configuration
ENV_NAME=${1:-dev}
AWS_ACCOUNT=${2:-$(aws sts get-caller-identity --query Account --output text)}
AWS_REGION=${3:-ap-northeast-1}

echo "🚀 Deploying Slack MCP Server Main Infrastructure (App Runner)"
echo "   Environment: $ENV_NAME"
echo "   Account: $AWS_ACCOUNT"
echo "   Region: $AWS_REGION"
echo "   🔒 HTTPS: Automatic with App Runner (*.awsapprunner.com)"
echo ""

# Check prerequisites
echo "📋 Checking prerequisites..."

if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI is not installed"
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo "❌ npm is not installed"
    exit 1
fi

if ! command -v cdk &> /dev/null; then
    echo "❌ AWS CDK is not installed. Please install it with: npm install -g aws-cdk"
    exit 1
fi

# Check if prerequisites stack exists
echo "🔍 Checking prerequisites stack..."
if ! aws cloudformation describe-stacks --stack-name SlackMcpPrerequisites-$ENV_NAME --region $AWS_REGION >/dev/null 2>&1; then
    echo "❌ Prerequisites stack not found. Please run ./deploy-prerequisites.sh first"
    exit 1
fi

# Get ECR repository URI from prerequisites stack
ECR_URI=$(aws cloudformation describe-stacks \
    --stack-name SlackMcpPrerequisites-$ENV_NAME \
    --region $AWS_REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`ECRRepositoryURI`].OutputValue' \
    --output text)

if [ -z "$ECR_URI" ]; then
    echo "❌ Could not get ECR repository URI from prerequisites stack"
    exit 1
fi

echo "✅ Prerequisites stack found"
echo "📦 ECR Repository: $ECR_URI"

# Check if Docker image exists in ECR
echo "🔍 Checking if Docker image exists in ECR..."
if ! aws ecr describe-images --repository-name "slack-mcp-server-$ENV_NAME" --region $AWS_REGION >/dev/null 2>&1; then
    echo "❌ No Docker image found in ECR. Please build and push your image first:"
    echo "   docker build -t slack-mcp-server ."
    echo "   aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_URI"
    echo "   docker tag slack-mcp-server:latest $ECR_URI:latest"
    echo "   docker push $ECR_URI:latest"
    exit 1
fi

echo "✅ Docker image found in ECR"

# Clean up existing main stack if it exists
echo "🔍 Checking for existing main stack..."
if aws cloudformation describe-stacks --stack-name SlackMcpStack-$ENV_NAME --region $AWS_REGION >/dev/null 2>&1; then
    echo "⚠️  Main stack 'SlackMcpStack-$ENV_NAME' already exists"
    echo "📝 Note: App Runner updates are handled through the service, not stack recreation"
    echo "   The stack will be updated with new configuration"
fi

# Clean up existing DynamoDB table if it exists
echo "🔍 Checking for existing DynamoDB table..."
TABLE_NAME="slack-mcp-tokens-$ENV_NAME"
if aws dynamodb describe-table --table-name "$TABLE_NAME" --region $AWS_REGION >/dev/null 2>&1; then
    echo "⚠️  DynamoDB table '$TABLE_NAME' already exists"
    echo "🗑️  Deleting existing DynamoDB table..."
    aws dynamodb delete-table --table-name "$TABLE_NAME" --region $AWS_REGION
    
    echo "⏳ Waiting for table deletion to complete..."
    aws dynamodb wait table-not-exists --table-name "$TABLE_NAME" --region $AWS_REGION
    if [ $? -eq 0 ]; then
        echo "✅ DynamoDB table deleted successfully"
    else
        echo "❌ Failed to delete DynamoDB table"
        exit 1
    fi
fi

# Install Node.js dependencies
echo "📦 Installing Node.js dependencies..."
npm install

# Bootstrap CDK (if needed)
echo "🔧 Bootstrapping CDK..."
cdk bootstrap aws://$AWS_ACCOUNT/$AWS_REGION

# Build TypeScript
echo "🔨 Building TypeScript..."
npm run build

# Deploy the main infrastructure stack
echo "🚀 Deploying main infrastructure..."
cdk deploy SlackMcpStack-$ENV_NAME \
    --context env=$ENV_NAME \
    --context account=$AWS_ACCOUNT \
    --context region=$AWS_REGION \
    --require-approval never

if [ $? -ne 0 ]; then
    echo "❌ Infrastructure deployment failed"
    exit 1
fi

# Get outputs
echo ""
echo "📋 Infrastructure deployment completed!"
APP_RUNNER_URL=$(aws cloudformation describe-stacks \
    --stack-name SlackMcpStack-$ENV_NAME \
    --region $AWS_REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`AppRunnerServiceUrl`].OutputValue' \
    --output text)

APP_RUNNER_ARN=$(aws cloudformation describe-stacks \
    --stack-name SlackMcpStack-$ENV_NAME \
    --region $AWS_REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`AppRunnerServiceArn`].OutputValue' \
    --output text)

echo "🌐 App Runner Service URL: $APP_RUNNER_URL"
echo "🔗 App Runner Service ARN: $APP_RUNNER_ARN"

# App Runner always provides HTTPS
PROTOCOL="https"

# Update service base URL parameter with App Runner URL
echo ""
echo "🔄 Updating service base URL parameter..."
# Remove the https:// prefix that's already included in the output
SERVICE_URL=$(echo $APP_RUNNER_URL | sed 's|https://||')
aws ssm put-parameter \
    --name "/slack-mcp/$ENV_NAME/service-base-url" \
    --value "https://$SERVICE_URL" \
    --type "String" \
    --overwrite \
    --region $AWS_REGION

if [ $? -eq 0 ]; then
    echo "✅ Service base URL parameter updated successfully"
else
    echo "⚠️  Failed to update service base URL parameter (non-critical)"
fi

echo ""
echo "📝 Next steps:"
echo "   1. Update your Slack app redirect URL to:"
echo "      $APP_RUNNER_URL/oauth/callback"
echo ""
echo "   2. Test the deployment:"
echo "      curl $APP_RUNNER_URL/health"
echo ""
echo "   3. If you need to update Slack credentials:"
echo "      aws ssm put-parameter --name '/slack-mcp/$ENV_NAME/client-id' --value 'your-client-id' --type 'String' --overwrite"
echo "      aws ssm put-parameter --name '/slack-mcp/$ENV_NAME/client-secret' --value 'your-client-secret' --type 'SecureString' --overwrite"
echo ""
echo "   4. To configure custom domain (optional):"
echo "      - Go to App Runner console"
echo "      - Select your service: slack-mcp-server-$ENV_NAME"
echo "      - Click 'Custom domains' tab"
echo "      - Add your domain and follow DNS configuration steps"