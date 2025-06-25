#!/bin/bash

# Prerequisites Deployment Script for Slack MCP Server

set -e

# Configuration
ENV_NAME=${1:-dev}
AWS_ACCOUNT=${2:-$(aws sts get-caller-identity --query Account --output text)}
AWS_REGION=${3:-ap-northeast-1}

echo "🚀 Deploying Slack MCP Server Prerequisites"
echo "   Environment: $ENV_NAME"
echo "   Account: $AWS_ACCOUNT"
echo "   Region: $AWS_REGION"
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

# Install Node.js dependencies
echo "📦 Installing Node.js dependencies..."
npm install

# Bootstrap CDK (if needed)
echo "🔧 Bootstrapping CDK..."
cdk bootstrap aws://$AWS_ACCOUNT/$AWS_REGION

# Build TypeScript
echo "🔨 Building TypeScript..."
npm run build

# Check for existing resources and clean up if needed
echo "🔍 Checking for existing resources..."

# Check if ECR repository exists
if aws ecr describe-repositories --repository-names "slack-mcp-server-$ENV_NAME" --region $AWS_REGION >/dev/null 2>&1; then
    echo "⚠️  ECR repository 'slack-mcp-server-$ENV_NAME' already exists"
    echo "🗑️  Deleting existing ECR repository..."
    aws ecr delete-repository --repository-name "slack-mcp-server-$ENV_NAME" --region $AWS_REGION --force
    if [ $? -eq 0 ]; then
        echo "✅ ECR repository deleted successfully"
    else
        echo "❌ Failed to delete ECR repository"
        exit 1
    fi
fi

# Check if Parameter Store parameters exist and delete them
for param in "client-id" "client-secret" "service-base-url"; do
    param_name="/slack-mcp/$ENV_NAME/$param"
    if aws ssm get-parameter --name "$param_name" --region $AWS_REGION >/dev/null 2>&1; then
        echo "⚠️  Parameter '$param_name' already exists"
        echo "🗑️  Deleting existing parameter..."
        aws ssm delete-parameter --name "$param_name" --region $AWS_REGION
        if [ $? -eq 0 ]; then
            echo "✅ Parameter '$param_name' deleted successfully"
        else
            echo "❌ Failed to delete parameter '$param_name'"
            exit 1
        fi
    fi
done

# Check if prerequisites stack exists and delete it
if aws cloudformation describe-stacks --stack-name SlackMcpPrerequisites-$ENV_NAME --region $AWS_REGION >/dev/null 2>&1; then
    echo "⚠️  Prerequisites stack 'SlackMcpPrerequisites-$ENV_NAME' already exists"
    echo "🗑️  Deleting existing prerequisites stack..."
    aws cloudformation delete-stack --stack-name SlackMcpPrerequisites-$ENV_NAME --region $AWS_REGION
    
    echo "⏳ Waiting for stack deletion to complete..."
    aws cloudformation wait stack-delete-complete --stack-name SlackMcpPrerequisites-$ENV_NAME --region $AWS_REGION
    if [ $? -eq 0 ]; then
        echo "✅ Prerequisites stack deleted successfully"
    else
        echo "❌ Failed to delete prerequisites stack"
        exit 1
    fi
fi

echo "✅ Resource cleanup completed"

# Deploy the prerequisites stack
echo "🚀 Deploying prerequisites stack..."
cdk deploy SlackMcpPrerequisites-$ENV_NAME \
    --app "node build/bin/prerequisites-app.js" \
    --context env=$ENV_NAME \
    --context account=$AWS_ACCOUNT \
    --context region=$AWS_REGION \
    --require-approval never

if [ $? -ne 0 ]; then
    echo "❌ Prerequisites deployment failed"
    exit 1
fi

# Get outputs
echo ""
echo "📋 Prerequisites deployment completed!"
ECR_URI=$(aws cloudformation describe-stacks \
    --stack-name SlackMcpPrerequisites-$ENV_NAME \
    --region $AWS_REGION \
    --query 'Stacks[0].Outputs[?OutputKey==`ECRRepositoryURI`].OutputValue' \
    --output text)

echo "📦 ECR Repository: $ECR_URI"
echo ""
echo "📝 Next steps:"
echo "   1. Build and push your Docker image:"
echo "      docker build -t slack-mcp-server ."
echo "      aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_URI"
echo "      docker tag slack-mcp-server:latest $ECR_URI:latest"
echo "      docker push $ECR_URI:latest"
echo ""
echo "   2. Set your Slack app credentials in Parameter Store:"
echo "      aws ssm put-parameter --name '/slack-mcp/$ENV_NAME/client-id' --value 'your-client-id' --type 'String' --overwrite"
echo "      aws ssm put-parameter --name '/slack-mcp/$ENV_NAME/client-secret' --value 'your-client-secret' --type 'SecureString' --overwrite"
echo ""
echo "   3. Deploy the main infrastructure:"
echo "      ./deploy.sh $ENV_NAME"