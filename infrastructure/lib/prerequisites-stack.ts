/**
 * Prerequisites Stack - Creates Parameter Store parameters and ECR repository
 * This should be deployed before the main Slack MCP stack
 */

import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as ssm from 'aws-cdk-lib/aws-ssm';

export interface PrerequisitesStackProps extends cdk.StackProps {
  envName: string;
}

export class PrerequisitesStack extends cdk.Stack {
  private readonly envName: string;
  public readonly ecrRepository: ecr.Repository;
  public readonly parameters: {
    clientId: ssm.StringParameter;
    clientSecret: ssm.StringParameter;
    serviceBaseUrl: ssm.StringParameter;
  };

  constructor(scope: Construct, id: string, props: PrerequisitesStackProps) {
    super(scope, id, props);

    this.envName = props.envName;

    // Create ECR repository
    this.ecrRepository = this.createEcrRepository();

    // Create Parameter Store parameters
    this.parameters = this.createParameterStoreParameters();

    // Output important values
    this.createOutputs();
  }

  private createEcrRepository(): ecr.Repository {
    return new ecr.Repository(this, 'SlackMcpRepository', {
      repositoryName: `slack-mcp-server-${this.envName}`,
      removalPolicy: cdk.RemovalPolicy.RETAIN, // Keep repository for reuse
      // Image scanning and lifecycle rules removed for faster deployment
    });
  }

  private createParameterStoreParameters(): {
    clientId: ssm.StringParameter;
    clientSecret: ssm.StringParameter;
    serviceBaseUrl: ssm.StringParameter;
  } {
    // Create placeholder parameters - actual values should be set manually
    const clientId = new ssm.StringParameter(this, 'SlackClientIdParameter', {
      parameterName: `/slack-mcp/${this.envName}/client-id`,
      stringValue: 'REPLACE_WITH_ACTUAL_CLIENT_ID',
      description: 'Slack application client ID',
    });

    const clientSecret = new ssm.StringParameter(this, 'SlackClientSecretParameter', {
      parameterName: `/slack-mcp/${this.envName}/client-secret`,
      stringValue: 'REPLACE_WITH_ACTUAL_CLIENT_SECRET',
      description: 'Slack application client secret',
    });

    // Service base URL will be populated by main stack
    const serviceBaseUrl = new ssm.StringParameter(this, 'ServiceBaseUrlParameter', {
      parameterName: `/slack-mcp/${this.envName}/service-base-url`,
      stringValue: 'WILL_BE_POPULATED_BY_MAIN_STACK',
      description: 'Service base URL for OAuth callbacks',
    });

    return { clientId, clientSecret, serviceBaseUrl };
  }

  private createOutputs(): void {
    new cdk.CfnOutput(this, 'ECRRepositoryURI', {
      value: this.ecrRepository.repositoryUri,
      description: 'ECR repository URI for container images',
      exportName: `SlackMcp-${this.envName}-ECRRepositoryURI`,
    });

    new cdk.CfnOutput(this, 'ECRRepositoryName', {
      value: this.ecrRepository.repositoryName,
      description: 'ECR repository name',
      exportName: `SlackMcp-${this.envName}-ECRRepositoryName`,
    });

    new cdk.CfnOutput(this, 'ParameterStorePrefix', {
      value: `/slack-mcp/${this.envName}/`,
      description: 'Parameter Store prefix for configuration',
      exportName: `SlackMcp-${this.envName}-ParameterStorePrefix`,
    });
  }
}