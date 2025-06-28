# Slack MCP Server - Deployment Guide (App Runner)

## Quick Start

### 1. Deploy Everything
```bash
# Deploy prerequisites and main stack
./deploy-all.sh
```

## App Runner Benefits

- **No Long Waits**: Deploys in minutes instead of hours
- **Built-in HTTPS**: Automatic SSL/TLS with AWS-managed certificates
- **Auto-scaling**: Handles traffic automatically
- **Simplified**: No load balancers or complex networking

## Detailed Deployment

### Option 1: Basic Deployment (Recommended)
```bash
# Uses App Runner's default HTTPS domain (*.awsapprunner.com)
./deploy.sh dev
```

### Option 2: Deploy to Specific Environment
```bash
# Deploy to production environment
./deploy.sh prod 123456789012 ap-northeast-1
```

### Option 3: Using CDK Directly
```bash
cd infrastructure
cdk deploy SlackMcpStack-dev --require-approval never
```

## Custom Domain Setup (Optional)

1. Deploy your service first:
   ```bash
   ./deploy.sh dev
   ```

2. After deployment, configure in App Runner console:
   - Go to App Runner service in AWS Console
   - Click on your service (slack-mcp-server-dev)
   - Go to "Custom domains" tab
   - Click "Add domain"
   - Enter your domain name
   - Follow the DNS configuration instructions provided by AWS

## Custom Domain Configuration

### How It Works

App Runner handles SSL/TLS certificates automatically for custom domains:
- AWS creates and manages the certificate
- No need to create or import certificates manually
- Automatic renewal before expiration
- Just configure DNS records as instructed

## Important Notes

1. **HTTPS is automatic** with App Runner default domain
2. **No certificate management needed** - AWS handles everything
3. **Custom domains** are optional and configured through console
4. App Runner provides better deployment experience than ECS+ALB

## Troubleshooting

### Service Not Starting
Check logs in App Runner console or:
```bash
aws apprunner list-services --region ap-northeast-1
```

### Stack Updates
```bash
# App Runner handles updates gracefully
./deploy.sh dev
```

### Clean Deployment
```bash
# Delete and redeploy if needed
cdk destroy SlackMcpStack-dev
./deploy.sh dev
```

## Service URLs

After deployment, you'll get:
- App Runner URL: `https://[random-id].awsapprunner.com`
- Use this URL in your Slack app OAuth redirect