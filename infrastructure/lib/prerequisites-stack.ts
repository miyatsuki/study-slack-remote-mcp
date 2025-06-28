/**
 * Prerequisites Stack - Creates Parameter Store parameters
 * This should be deployed before the main Slack MCP stack
 */

import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as ssm from 'aws-cdk-lib/aws-ssm';

export interface PrerequisitesStackProps extends cdk.StackProps {
  envName: string;
}

export class PrerequisitesStack extends cdk.Stack {
  private readonly envName: string;
  public readonly parameters: {
    clientId: ssm.StringParameter;
    clientSecret: ssm.StringParameter;
    serviceBaseUrl: ssm.StringParameter;
  };

  constructor(scope: Construct, id: string, props: PrerequisitesStackProps) {
    super(scope, id, props);

    this.envName = props.envName;

    // Create Parameter Store parameters
    this.parameters = this.createParameterStoreParameters();

    // Output important values
    this.createOutputs();
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
    new cdk.CfnOutput(this, 'ParameterStorePrefix', {
      value: `/slack-mcp/${this.envName}/`,
      description: 'Parameter Store prefix for configuration',
      exportName: `SlackMcp-${this.envName}-ParameterStorePrefix`,
    });

    new cdk.CfnOutput(this, 'ParametersNote', {
      value: 'Remember to update the parameter values with actual Slack app credentials',
      description: 'Important note about parameter configuration',
    });
  }
}