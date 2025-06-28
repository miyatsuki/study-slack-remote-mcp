/**
 * Slack MCP Server Infrastructure Stack - Using AWS App Runner
 */

import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as apprunner from 'aws-cdk-lib/aws-apprunner';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as ecr from 'aws-cdk-lib/aws-ecr';

export interface SlackMcpStackProps extends cdk.StackProps {
  envName: string;
}

export class SlackMcpStack extends cdk.Stack {
  private readonly envName: string;
  private readonly dynamodbTable: dynamodb.Table;
  private readonly ecrRepository: ecr.IRepository;
  private readonly instanceRole: iam.Role;
  private readonly accessRole: iam.Role;
  private readonly appRunnerService: apprunner.CfnService;

  constructor(scope: Construct, id: string, props: SlackMcpStackProps) {
    super(scope, id, props);

    this.envName = props.envName;

    // Create DynamoDB table for token storage
    this.dynamodbTable = this.createDynamodbTable();

    // Reference existing ECR repository from prerequisites stack
    this.ecrRepository = this.getExistingEcrRepository();

    // Create IAM roles for App Runner
    const roles = this.createIamRoles();
    this.instanceRole = roles.instance;
    this.accessRole = roles.access;

    // Create App Runner service
    this.appRunnerService = this.createAppRunnerService();

    // Output important values
    this.createOutputs();
  }

  private createDynamodbTable(): dynamodb.Table {
    return new dynamodb.Table(this, 'SlackMcpTokens', {
      tableName: `slack-mcp-tokens-${this.envName}`,
      partitionKey: {
        name: 'client_id',
        type: dynamodb.AttributeType.STRING,
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      pointInTimeRecovery: true,
      timeToLiveAttribute: 'expires_at',
    });
  }

  private getExistingEcrRepository(): ecr.IRepository {
    // Reference ECR repository created by prerequisites stack
    return ecr.Repository.fromRepositoryName(
      this,
      'ExistingSlackMcpRepository',
      `slack-mcp-server-${this.envName}`
    );
  }

  private createIamRoles(): {
    instance: iam.Role;
    access: iam.Role;
  } {
    // App Runner instance role (similar to ECS task role)
    const instanceRole = new iam.Role(this, 'SlackMcpAppRunnerInstanceRole', {
      assumedBy: new iam.ServicePrincipal('tasks.apprunner.amazonaws.com'),
    });

    // Add DynamoDB access
    instanceRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'dynamodb:GetItem',
          'dynamodb:PutItem',
          'dynamodb:DeleteItem',
          'dynamodb:Scan',
          'dynamodb:CreateTable',
          'dynamodb:DescribeTable',
        ],
        resources: [this.dynamodbTable.tableArn],
      })
    );

    // Note: Parameter Store access is handled automatically by App Runner when using runtimeEnvironmentSecrets

    // App Runner access role (for ECR access)
    const accessRole = new iam.Role(this, 'SlackMcpAppRunnerAccessRole', {
      assumedBy: new iam.ServicePrincipal('build.apprunner.amazonaws.com'),
    });

    // Add ECR access policy
    accessRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'ecr:BatchCheckLayerAvailability',
          'ecr:BatchGetImage',
          'ecr:GetDownloadUrlForLayer',
          'ecr:GetAuthorizationToken',
        ],
        resources: ['*'], // ECR requires * for GetAuthorizationToken
      })
    );

    return {
      instance: instanceRole,
      access: accessRole,
    };
  }


  private createAppRunnerService(): apprunner.CfnService {
    // Basic service configuration
    const serviceConfig = {
      serviceName: `slack-mcp-server-${this.envName}`,
      sourceConfiguration: {
        authenticationConfiguration: {
          accessRoleArn: this.accessRole.roleArn,
        },
        autoDeploymentsEnabled: false, // Manual deployments for more control
        imageRepository: {
          imageConfiguration: {
            port: '8080', // MCP server port
            runtimeEnvironmentVariables: [
              {
                name: 'DYNAMODB_TABLE_NAME',
                value: this.dynamodbTable.tableName,
              },
              {
                name: 'AWS_REGION',
                value: this.region,
              },
              {
                name: 'MCP_ENV',
                value: this.envName,
              },
              {
                name: 'DOCKER_ENV',
                value: 'true', // Ensure proxy is used
              },
              {
                name: 'TOKEN_STORAGE_PATH',
                value: '/app/data/slack_tokens.jsonl', // Fallback path
              },
            ],
            runtimeEnvironmentSecrets: [
              {
                name: 'SLACK_CLIENT_ID',
                valueFrom: `arn:aws:ssm:${this.region}:${this.account}:parameter/slack-mcp/${this.envName}/client-id`,
              },
              {
                name: 'SLACK_CLIENT_SECRET',
                valueFrom: `arn:aws:ssm:${this.region}:${this.account}:parameter/slack-mcp/${this.envName}/client-secret`,
              },
              {
                name: 'SERVICE_BASE_URL',
                valueFrom: `arn:aws:ssm:${this.region}:${this.account}:parameter/slack-mcp/${this.envName}/service-base-url`,
              },
            ],
          },
          imageIdentifier: `${this.ecrRepository.repositoryUri}:latest`,
          imageRepositoryType: 'ECR',
        },
      },
      instanceConfiguration: {
        cpu: '0.5 vCPU', // Increased for faster startup
        memory: '1 GB', // Increased for better performance
        instanceRoleArn: this.instanceRole.roleArn,
      },
      healthCheckConfiguration: {
        path: '/health',
        protocol: 'HTTP',
        interval: 30, // seconds - increased for startup time
        timeout: 20, // seconds - increased timeout
        healthyThreshold: 1, // faster to become healthy
        unhealthyThreshold: 3, // more lenient
      },
    };

    // Create App Runner service
    const service = new apprunner.CfnService(this, 'SlackMcpAppRunnerService', serviceConfig);

    return service;
  }

  private createOutputs(): void {
    // App Runner service URL
    new cdk.CfnOutput(this, 'AppRunnerServiceUrl', {
      value: `https://${this.appRunnerService.attrServiceUrl}`,
      description: 'URL of the App Runner service',
    });

    // Service ARN for reference
    new cdk.CfnOutput(this, 'AppRunnerServiceArn', {
      value: this.appRunnerService.attrServiceArn,
      description: 'ARN of the App Runner service',
    });

    // Note about custom domain
    new cdk.CfnOutput(this, 'CustomDomainNote', {
      value: 'To use a custom domain, configure it in the App Runner console after deployment',
      description: 'Instructions for custom domain setup',
    });
  }
}