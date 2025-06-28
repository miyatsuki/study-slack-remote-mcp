# Slack MCP Server - CDK Infrastructure

This directory contains the AWS CDK (Cloud Development Kit) infrastructure code for deploying the Slack MCP Server to AWS App Runner.

## 📁 File Structure

```
infrastructure/
├── bin/
│   └── app.ts                # CDK App entry point
├── lib/
│   └── slack-mcp-stack.ts    # Main infrastructure stack
├── package.json              # Node.js dependencies and scripts
├── tsconfig.json             # TypeScript configuration
├── cdk.json                  # CDK configuration
├── deploy.sh                 # Automated deployment script
└── README.md                 # This file
```

## 🏗️ Infrastructure Components

### Core Resources
- **App Runner Service**: Fully managed service for containerized applications
- **Auto-scaling**: Built-in auto-scaling based on traffic
- **Load Balancing**: Integrated load balancing (no ALB needed)
- **HTTPS**: Automatic SSL/TLS with AWS-managed certificates

### Storage & Configuration  
- **DynamoDB Table**: Token storage with TTL
- **ECR Repository**: Container image registry
- **Parameter Store**: Secure configuration management
- **CloudWatch Logs**: Centralized logging

### Security
- **IAM Roles**: Instance and access roles for App Runner
- **Built-in Security**: App Runner handles network security

## 🚀 Quick Deployment

```bash
# Deploy with default settings (dev environment)
./deploy.sh

# Deploy to specific environment
./deploy.sh prod 123456789012 ap-northeast-1

# Deploy with specific environment
./deploy.sh prod
```

## ⚙️ Configuration

### Environment Contexts

The stack supports multiple environments through CDK context:

```bash
cdk deploy SlackMcpStack-{env} --context env={env}
```

### Parameter Store Structure

```
/slack-mcp/{env}/
├── client-id          # Slack app client ID
├── client-secret      # Slack app client secret (SecureString)
└── service-base-url   # Service base URL for OAuth callbacks
```

## 🔐 HTTPS Configuration

App Runner provides automatic HTTPS with AWS-managed certificates:

### Default HTTPS (Recommended for most cases)

```bash
# Deploy with automatic HTTPS
./deploy.sh dev
# Service URL: https://[random-id].awsapprunner.com
```

### Custom Domain (Optional)

```bash
# Deploy with certificate for custom domain
export CERTIFICATE_ARN="arn:aws:acm:region:account:certificate/xxx"
./deploy.sh dev

# After deployment, configure custom domain in App Runner console
```

**App Runner Benefits:**
- ✅ Automatic HTTPS by default
- ✅ No load balancer management
- ✅ Fast deployments (minutes vs hours)
- ✅ Built-in auto-scaling

## 🔧 Manual Operations

### View Stack Outputs
```bash
aws cloudformation describe-stacks \
    --stack-name SlackMcpStack-dev \
    --query 'Stacks[0].Outputs'
```

### Update Service with New Image
```bash
# App Runner automatically detects new images if auto-deployment is enabled
# Or manually start deployment:
aws apprunner start-deployment \
    --service-arn $(aws cloudformation describe-stacks \
        --stack-name SlackMcpStack-dev \
        --query 'Stacks[0].Outputs[?OutputKey==`AppRunnerServiceArn`].OutputValue' \
        --output text)
```

### Check Service Status
```bash
aws apprunner describe-service \
    --service-arn $(aws cloudformation describe-stacks \
        --stack-name SlackMcpStack-dev \
        --query 'Stacks[0].Outputs[?OutputKey==`AppRunnerServiceArn`].OutputValue' \
        --output text)
```

## 🛠️ Development

### CDK Commands

```bash
# List all stacks
cdk list

# Show differences
cdk diff SlackMcpStack-dev

# Synthesize CloudFormation
cdk synth SlackMcpStack-dev

# Deploy without approval
cdk deploy SlackMcpStack-dev --require-approval=never
```

### Stack Customization

To modify the infrastructure:

1. Edit `lib/slack-mcp-stack.ts`
2. Build TypeScript: `npm run build`
3. Test changes with `cdk diff`
4. Deploy with `cdk deploy`

### Environment Variables

The deploy script recognizes these environment variables:

- `AWS_PROFILE`: AWS CLI profile to use
- `AWS_REGION`: Target AWS region
- `CDK_DEFAULT_ACCOUNT`: Default AWS account

## 🗑️ Cleanup

**Warning**: This will permanently delete all resources!

```bash
# Delete entire stack
cdk destroy SlackMcpStack-dev

# Delete all environments
cdk destroy SlackMcpStack-dev SlackMcpStack-staging SlackMcpStack-prod
```

## 🔍 Troubleshooting

### Common Issues

1. **Bootstrap required**: Run `cdk bootstrap` first
2. **Permission denied**: Check AWS credentials and IAM permissions
3. **Resource conflicts**: Use unique stack names per environment
4. **ECR image not found**: Ensure image is pushed to ECR repository

### Logs and Monitoring

```bash
# View App Runner service logs
aws logs tail /aws/apprunner/slack-mcp-server-dev/[service-id]/application --follow

# View service events
aws apprunner list-operations \
    --service-arn $(aws cloudformation describe-stacks \
        --stack-name SlackMcpStack-dev \
        --query 'Stacks[0].Outputs[?OutputKey==`AppRunnerServiceArn`].OutputValue' \
        --output text)
```

## 🔄 Migration from ECS/Fargate

If migrating from ECS/Fargate to App Runner:

1. App Runner replaces ECS cluster, service, task definition, and ALB
2. Security groups and VPC configuration are handled automatically
3. Health checks are simplified (just specify path)
4. HTTPS is automatic without certificate management
5. Deployment is much faster with no consistency check delays