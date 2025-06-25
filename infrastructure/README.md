# Slack MCP Server - CDK Infrastructure

This directory contains the AWS CDK (Cloud Development Kit) infrastructure code for deploying the Slack MCP Server to AWS Fargate.

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
- **ECS Cluster**: Fargate cluster for running containers
- **ECS Service**: Manages desired number of tasks
- **Task Definition**: Container specification with resource limits
- **Application Load Balancer**: Internet-facing load balancer
- **Target Group**: Health check and traffic routing

### Storage & Configuration  
- **DynamoDB Table**: Token storage with TTL
- **ECR Repository**: Container image registry
- **Parameter Store**: Secure configuration management
- **CloudWatch Logs**: Centralized logging

### Security
- **Security Groups**: Network access control
- **IAM Roles**: Task execution and runtime permissions
- **VPC**: Network isolation (new or existing)

## 🚀 Quick Deployment

```bash
# Deploy with default settings (dev environment)
./deploy.sh

# Deploy to specific environment
./deploy.sh prod 123456789012 ap-northeast-1
```

## ⚙️ Configuration

### Environment Contexts

The stack supports multiple environments through CDK context:

```bash
cdk deploy SlackMcpStack-{env} --context env={env}
```

### VPC Configuration

**Option 1: Use existing VPC**
```bash
cdk deploy --context vpc_id=vpc-12345678
```

**Option 2: Create new VPC** (default)
- 2 AZs with public and private subnets
- NAT Gateway for private subnet egress

### Parameter Store Structure

```
/slack-mcp/{env}/
├── client-id          # Slack app client ID
├── client-secret      # Slack app client secret (SecureString)
├── service-base-url   # Service base URL for OAuth callbacks
└── certificate-arn    # SSL certificate ARN (optional)
```

## 🔐 HTTPS Configuration

The stack supports HTTPS with flexible certificate options:

### Option 1: Self-Signed Certificate (Development)

```bash
# Generate and import self-signed certificate
./generate-self-signed-cert.sh

# Deploy with certificate ARN
export CERTIFICATE_ARN="arn:aws:acm:region:account:certificate/xxx"
cdk deploy SlackMcpStack-dev

# Or use CDK context
cdk deploy SlackMcpStack-dev --context certificateArn="arn:aws:acm:..."
```

### Option 2: ACM Domain Certificate (Production)

```bash
# Deploy with your domain (requires DNS validation)
export DOMAIN_NAME="your-domain.com"
cdk deploy SlackMcpStack-dev

# Or use CDK context
cdk deploy SlackMcpStack-dev --context domainName="your-domain.com"
```

### Option 3: HTTP Only (Default)

If no certificate is configured, the stack deploys with HTTP-only access.

**HTTPS Benefits:**
- ✅ Secure OAuth callback URLs
- ✅ Encrypted communication
- ✅ Compatible with Slack App requirements

**Note**: Self-signed certificates will show browser warnings. For production, use a real domain with ACM.

## 🔧 Manual Operations

### View Stack Outputs
```bash
aws cloudformation describe-stacks \
    --stack-name SlackMcpStack-dev \
    --query 'Stacks[0].Outputs'
```

### Update Service with New Image
```bash
aws ecs update-service \
    --cluster slack-mcp-cluster-dev \
    --service slack-mcp-service-dev \
    --force-new-deployment
```

### Check Service Status
```bash
aws ecs describe-services \
    --cluster slack-mcp-cluster-dev \
    --services slack-mcp-service-dev
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

# Deploy with approval
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
4. **VPC not found**: Ensure VPC ID exists in the target region

### Logs and Monitoring

```bash
# View ECS service events
aws ecs describe-services \
    --cluster slack-mcp-cluster-dev \
    --services slack-mcp-service-dev \
    --query 'services[0].events'

# View CloudWatch logs
aws logs tail /ecs/slack-mcp-server-dev --follow
```