#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { PrerequisitesStack } from '../lib/prerequisites-stack';

const app = new cdk.App();

// Get environment configuration
const envName = app.node.tryGetContext('env') || 'dev';
const account = app.node.tryGetContext('account') || process.env.CDK_DEFAULT_ACCOUNT;
const region = app.node.tryGetContext('region') || process.env.CDK_DEFAULT_REGION || 'ap-northeast-1';

console.log(`Deploying prerequisites for environment: ${envName}`);

new PrerequisitesStack(app, `SlackMcpPrerequisites-${envName}`, {
  env: {
    account,
    region,
  },
  envName,
});