/**
 * Slack MCP Server Infrastructure Stack - Using AWS App Runner with GitHub
 */

import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as apprunner from 'aws-cdk-lib/aws-apprunner';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';

export interface SlackMcpStackProps extends cdk.StackProps {
  envName: string;
}

export class SlackMcpStack extends cdk.Stack {
  private readonly envName: string;
  private readonly dynamodbTable: dynamodb.Table;
  private readonly instanceRole: iam.Role;
  private readonly appRunnerService: apprunner.CfnService;

  constructor(scope: Construct, id: string, props: SlackMcpStackProps) {
    super(scope, id, props);

    this.envName = props.envName;

    // Create DynamoDB table for token storage
    this.dynamodbTable = this.createDynamodbTable();

    // Create IAM role for App Runner
    this.instanceRole = this.createInstanceRole();

    // Create App Runner service with GitHub source
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

  private createInstanceRole(): iam.Role {
    // App Runner instance role
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

    // Add SSM Parameter Store access for secrets
    instanceRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'ssm:GetParameter',
          'ssm:GetParameters',
          'ssm:GetParametersByPath',
        ],
        resources: [
          `arn:aws:ssm:${this.region}:${this.account}:parameter/slack-mcp/${this.envName}/*`,
        ],
      })
    );

    return instanceRole;
  }


  private createAppRunnerService(): apprunner.CfnService {
    // Get existing GitHub connection ARN (created manually)
    const githubConnectionArn = `arn:aws:apprunner:${this.region}:${this.account}:connection/gh-connection/b1c7ae218ff843ddaeb34ac4c66b35f8`;

    // Basic service configuration with GitHub source
    const serviceConfig = {
      serviceName: `slack-mcp-server-${this.envName}`,
      sourceConfiguration: {
        authenticationConfiguration: {
          connectionArn: githubConnectionArn,
        },
        autoDeploymentsEnabled: false, // Manual deployments for more control
        codeRepository: {
          repositoryUrl: 'https://github.com/miyatsuki/study-slack-remote-mcp',
          sourceCodeVersion: {
            type: 'BRANCH',
            value: 'main',
          },
          codeConfiguration: {
            configurationSource: 'REPOSITORY', // Use apprunner.yaml from repository
          },
        },
      },
      instanceConfiguration: {
        cpu: '0.25 vCPU', // Using minimum for cost efficiency
        memory: '0.5 GB',
        instanceRoleArn: this.instanceRole.roleArn,
      },
      healthCheckConfiguration: {
        path: '/health',
        protocol: 'HTTP',
        interval: 30, // seconds
        timeout: 20, // seconds
        healthyThreshold: 1,
        unhealthyThreshold: 3,
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