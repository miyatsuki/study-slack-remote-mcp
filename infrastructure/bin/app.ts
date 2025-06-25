#!/usr/bin/env node
/**
 * AWS CDK App for Slack MCP Server Infrastructure
 */

import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { SlackMcpStack } from '../lib/slack-mcp-stack';

const app = new cdk.App();

// Get environment configuration
const envName = app.node.tryGetContext('env') || 'dev';
const account = app.node.tryGetContext('account') || process.env.CDK_DEFAULT_ACCOUNT;
const region = app.node.tryGetContext('region') || process.env.CDK_DEFAULT_REGION || 'ap-northeast-1';

// Create the Slack MCP stack
new SlackMcpStack(app, `SlackMcpStack-${envName}`, {
  env: { account, region },
  envName,
  description: `Slack MCP Server infrastructure for ${envName} environment`,
});

app.synth();