/**
 * Slack MCP Server Infrastructure Stack
 */

import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as ssm from 'aws-cdk-lib/aws-ssm';
import * as acm from 'aws-cdk-lib/aws-certificatemanager';

export interface SlackMcpStackProps extends cdk.StackProps {
  envName: string;
}

export class SlackMcpStack extends cdk.Stack {
  private readonly envName: string;
  private readonly vpc: ec2.IVpc;
  private readonly securityGroups: {
    alb: ec2.SecurityGroup;
    fargate: ec2.SecurityGroup;
  };
  private readonly dynamodbTable: dynamodb.Table;
  private readonly ecrRepository: ecr.IRepository;
  private readonly iamRoles: {
    execution: iam.Role;
    task: iam.Role;
  };
  private readonly alb: elbv2.ApplicationLoadBalancer;
  private targetGroup: elbv2.ApplicationTargetGroup;
  private healthTargetGroup: elbv2.ApplicationTargetGroup;
  private readonly certificate?: acm.ICertificate;
  private readonly ecsCluster: ecs.Cluster;
  private readonly taskDefinition: ecs.FargateTaskDefinition;
  private readonly ecsService: ecs.FargateService;

  constructor(scope: Construct, id: string, props: SlackMcpStackProps) {
    super(scope, id, props);

    this.envName = props.envName;

    // Create or reference VPC
    this.vpc = this.createVpc();

    // Create Security Groups
    this.securityGroups = this.createSecurityGroups();

    // Create DynamoDB table for token storage
    this.dynamodbTable = this.createDynamodbTable();

    // Reference existing ECR repository from prerequisites stack
    this.ecrRepository = this.getExistingEcrRepository();

    // Parameter Store parameters are accessed via environment variables at runtime
    // No need to reference them in CloudFormation template

    // Create IAM roles
    this.iamRoles = this.createIamRoles();

    // Create or reference SSL certificate for HTTPS
    this.certificate = this.createOrReferenceCertificate();

    // Create Application Load Balancer with HTTPS support
    this.alb = this.createApplicationLoadBalancer();

    // Create ECS Cluster
    this.ecsCluster = this.createEcsCluster();

    // Create ECS Task Definition
    this.taskDefinition = this.createTaskDefinition();

    // Create ECS Service
    this.ecsService = this.createEcsService();

    // Service base URL will be set manually or via deployment script
    // Automatic Parameter Store update removed for faster deployments
    
    // Output important values
    this.createOutputs();
  }

  private createVpc(): ec2.IVpc {
    // Use default VPC for faster deployment and lower cost
    return ec2.Vpc.fromLookup(this, 'DefaultVpc', {
      isDefault: true,
    });
  }

  private createSecurityGroups(): {
    alb: ec2.SecurityGroup;
    fargate: ec2.SecurityGroup;
  } {
    // ALB Security Group
    const albSg = new ec2.SecurityGroup(this, 'SlackMcpAlbSecurityGroup', {
      vpc: this.vpc,
      description: 'Security group for Slack MCP ALB',
      allowAllOutbound: true,
    });

    albSg.addIngressRule(
      ec2.Peer.anyIpv4(),
      ec2.Port.tcp(80),
      'Allow HTTP traffic'
    );

    albSg.addIngressRule(
      ec2.Peer.anyIpv4(),
      ec2.Port.tcp(443),
      'Allow HTTPS traffic'
    );

    // Fargate Security Group
    const fargateSg = new ec2.SecurityGroup(this, 'SlackMcpFargateSecurityGroup', {
      vpc: this.vpc,
      description: 'Security group for Slack MCP Fargate tasks',
      allowAllOutbound: true,
    });

    // Allow traffic from ALB to application container ports
    fargateSg.addIngressRule(
      albSg,
      ec2.Port.tcp(8001),
      'Allow traffic from ALB to application port 8001'
    );
    
    fargateSg.addIngressRule(
      albSg,
      ec2.Port.tcp(8002),
      'Allow traffic from ALB to health check port 8002'
    );

    return {
      alb: albSg,
      fargate: fargateSg,
    };
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
    execution: iam.Role;
    task: iam.Role;
  } {
    // ECS Task Execution Role
    const taskExecutionRole = new iam.Role(this, 'SlackMcpTaskExecutionRole', {
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AmazonECSTaskExecutionRolePolicy'),
      ],
    });

    // Add Parameter Store access for secrets
    taskExecutionRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ['ssm:GetParameter', 'ssm:GetParameters'],
        resources: [
          `arn:aws:ssm:${this.region}:${this.account}:parameter/slack-mcp/${this.envName}/*`,
        ],
      })
    );

    // ECS Task Role
    const taskRole = new iam.Role(this, 'SlackMcpTaskRole', {
      assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
    });

    // Add DynamoDB access
    taskRole.addToPolicy(
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

    // Add Parameter Store access for runtime config
    taskRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ['ssm:GetParameter', 'ssm:GetParameters'],
        resources: [
          `arn:aws:ssm:${this.region}:${this.account}:parameter/slack-mcp/${this.envName}/*`,
        ],
      })
    );

    return {
      execution: taskExecutionRole,
      task: taskRole,
    };
  }

  private createOrReferenceCertificate(): acm.ICertificate | undefined {
    // Check if certificate ARN is provided via context or environment
    const contextCertArn = this.node.tryGetContext('certificateArn');
    const envCertArn = process.env.CERTIFICATE_ARN;
    const certArn = contextCertArn || envCertArn;
    
    console.log('🔍 Certificate detection:');
    console.log('   Context certificateArn:', contextCertArn);
    console.log('   Environment CERTIFICATE_ARN:', envCertArn);
    console.log('   Final certArn:', certArn);
    
    if (certArn) {
      console.log('✅ Certificate found - creating HTTPS listener');
      // Use existing certificate ARN (either self-signed or ACM)
      return acm.Certificate.fromCertificateArn(
        this,
        'ExistingCertificate',
        certArn
      );
    }

    // Check if domain name is provided for ACM certificate
    const domainName = this.node.tryGetContext('domainName') || 
                      process.env.DOMAIN_NAME;
    
    if (domainName) {
      // Create ACM certificate with DNS validation
      return new acm.Certificate(this, 'AcmCertificate', {
        domainName: domainName,
        validation: acm.CertificateValidation.fromDns(),
      });
    }

    // No certificate configuration found - HTTPS will be disabled
    console.warn('⚠️  No certificate configuration found. HTTPS will be disabled.');
    console.warn('   To enable HTTPS, either:');
    console.warn('   1. Set CERTIFICATE_ARN environment variable with imported self-signed cert ARN');
    console.warn('   2. Set DOMAIN_NAME environment variable for ACM certificate');
    console.warn('   3. Use CDK context: --context certificateArn=arn:aws:acm:...');
    console.warn('   4. Use CDK context: --context domainName=your-domain.com');
    
    return undefined;
  }

  private createApplicationLoadBalancer(): elbv2.ApplicationLoadBalancer {
    const alb = new elbv2.ApplicationLoadBalancer(this, 'SlackMcpAlb', {
      vpc: this.vpc,
      internetFacing: true,
      securityGroup: this.securityGroups.alb,
    });

    // Create target group for application
    this.targetGroup = new elbv2.ApplicationTargetGroup(this, 'SlackMcpTargetGroup', {
      vpc: this.vpc,
      port: 8001,  // Application port
      protocol: elbv2.ApplicationProtocol.HTTP,
      targetType: elbv2.TargetType.IP,
      healthCheck: {
        enabled: true,
        path: '/health',
        port: '8002',  // Use port 8002 for health checks
        protocol: elbv2.Protocol.HTTP,
        interval: cdk.Duration.seconds(60),
        timeout: cdk.Duration.seconds(10),
        healthyThresholdCount: 2,
        unhealthyThresholdCount: 10,  // Very lenient to avoid issues
      },
    });

    if (this.certificate) {
      // HTTPS is enabled - create HTTP listener that redirects to HTTPS
      new elbv2.ApplicationListener(this, 'SlackMcpHttpListener', {
        loadBalancer: alb,
        port: 80,
        protocol: elbv2.ApplicationProtocol.HTTP,
        defaultAction: elbv2.ListenerAction.redirect({
          protocol: 'HTTPS',
          port: '443',
          permanent: true,
        }),
      });

      // Create HTTPS listener with certificate
      new elbv2.ApplicationListener(this, 'SlackMcpHttpsListener', {
        loadBalancer: alb,
        port: 443,
        protocol: elbv2.ApplicationProtocol.HTTPS,
        certificates: [this.certificate],
        defaultAction: elbv2.ListenerAction.forward([this.targetGroup]),
      });
      
      console.log('✅ HTTPS listener created with certificate');
    } else {
      // HTTPS is disabled - create HTTP listener only
      new elbv2.ApplicationListener(this, 'SlackMcpHttpListener', {
        loadBalancer: alb,
        port: 80,
        protocol: elbv2.ApplicationProtocol.HTTP,
        defaultAction: elbv2.ListenerAction.forward([this.targetGroup]),
      });
      
      console.log('ℹ️  HTTP-only listener created (no certificate configured)');
    }

    return alb;
  }

  private createEcsCluster(): ecs.Cluster {
    return new ecs.Cluster(this, 'SlackMcpCluster', {
      vpc: this.vpc,
      clusterName: `slack-mcp-cluster-${this.envName}`,
    });
  }

  private createTaskDefinition(): ecs.FargateTaskDefinition {
    const taskDefinition = new ecs.FargateTaskDefinition(this, 'SlackMcpTaskDefinition', {
      family: `slack-mcp-server-${this.envName}`,
      cpu: 256,
      memoryLimitMiB: 512,
      executionRole: this.iamRoles.execution,
      taskRole: this.iamRoles.task,
    });

    // Add application container
    const container = taskDefinition.addContainer('slack-mcp-server', {
      image: ecs.ContainerImage.fromEcrRepository(this.ecrRepository, 'latest'),
      essential: true,
      environment: {
        DYNAMODB_TABLE_NAME: this.dynamodbTable.tableName,
        AWS_REGION: this.region,
        MCP_ENV: this.envName,
        // Parameter Store parameter names (values will be fetched at runtime)
        SLACK_CLIENT_ID_PARAM: `/slack-mcp/${this.envName}/client-id`,
        SLACK_CLIENT_SECRET_PARAM: `/slack-mcp/${this.envName}/client-secret`,
        SERVICE_BASE_URL_PARAM: `/slack-mcp/${this.envName}/service-base-url`,
      },
      logging: ecs.LogDrivers.awsLogs({
        streamPrefix: 'ecs',
        // Log group will be auto-created by ECS
      }),
      // Health check disabled to avoid deployment issues
    });

    container.addPortMappings({
      containerPort: 8001,  // Application port
      protocol: ecs.Protocol.TCP,
    });
    
    container.addPortMappings({
      containerPort: 8002,  // Health check port
      protocol: ecs.Protocol.TCP,
    });

    return taskDefinition;
  }

  private createEcsService(): ecs.FargateService {
    const service = new ecs.FargateService(this, 'SlackMcpService', {
      cluster: this.ecsCluster,
      taskDefinition: this.taskDefinition,
      serviceName: `slack-mcp-service-${this.envName}`,
      desiredCount: 1,
      securityGroups: [this.securityGroups.fargate],
      assignPublicIp: true,
    });

    // Attach to load balancer
    service.attachToApplicationTargetGroup(this.targetGroup);

    return service;
  }


  private createOutputs(): void {
    // Only essential outputs for deployment script
    new cdk.CfnOutput(this, 'LoadBalancerDNS', {
      value: this.alb.loadBalancerDnsName,
      description: 'DNS name of the Application Load Balancer',
    });
  }
}