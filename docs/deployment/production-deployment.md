# Production Deployment Guide

## Table of Contents
1. [Infrastructure Overview](#infrastructure-overview)
2. [AWS Deployment](#aws-deployment)
3. [Environment Configuration](#environment-configuration)
4. [Database Setup](#database-setup)
5. [Application Deployment](#application-deployment)
6. [SSL/TLS Configuration](#ssltls-configuration)
7. [Monitoring Setup](#monitoring-setup)
8. [Backup Strategy](#backup-strategy)
9. [Scaling Considerations](#scaling-considerations)
10. [Rollback Procedures](#rollback-procedures)

## Infrastructure Overview

### Architecture Diagram
```
┌─────────────────────────────────────────────────────────────┐
│                         CloudFlare                           │
│                      (CDN & DDoS Protection)                 │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    Application Load Balancer                 │
│                         (AWS ALB)                           │
└─────────────────────────────────────────────────────────────┘
                    │                        │
                    ▼                        ▼
        ┌──────────────────┐       ┌──────────────────┐
        │   ECS Fargate    │       │   ECS Fargate    │
        │  Frontend (3x)   │       │   Backend (3x)   │
        └──────────────────┘       └──────────────────┘
                    │                        │
                    └────────────┬───────────┘
                                 ▼
                    ┌─────────────────────────┐
                    │      RDS PostgreSQL     │
                    │    with TimescaleDB     │
                    │   (Multi-AZ Replica)    │
                    └─────────────────────────┘
                                 │
                    ┌─────────────────────────┐
                    │    ElastiCache Redis    │
                    │    (Cluster Mode)       │
                    └─────────────────────────┘
```

### Technology Stack
- **Cloud Provider**: AWS
- **Container Orchestration**: ECS Fargate
- **Database**: RDS PostgreSQL with TimescaleDB
- **Cache**: ElastiCache Redis
- **CDN**: CloudFlare
- **CI/CD**: GitHub Actions
- **Monitoring**: CloudWatch, Prometheus, Grafana
- **Secrets**: AWS Secrets Manager

## AWS Deployment

### Prerequisites
1. AWS Account with appropriate permissions
2. AWS CLI configured
3. Terraform installed (optional but recommended)
4. Docker images pushed to ECR

### Setting Up AWS Infrastructure

#### 1. Create VPC and Networking
```bash
# Using AWS CLI
aws ec2 create-vpc --cidr-block 10.0.0.0/16 --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=afwd-prod-vpc}]'

# Create public subnets (for ALB)
aws ec2 create-subnet --vpc-id <vpc-id> --cidr-block 10.0.1.0/24 --availability-zone us-east-1a
aws ec2 create-subnet --vpc-id <vpc-id> --cidr-block 10.0.2.0/24 --availability-zone us-east-1b

# Create private subnets (for ECS tasks)
aws ec2 create-subnet --vpc-id <vpc-id> --cidr-block 10.0.10.0/24 --availability-zone us-east-1a
aws ec2 create-subnet --vpc-id <vpc-id> --cidr-block 10.0.20.0/24 --availability-zone us-east-1b
```

#### 2. Terraform Configuration (Recommended)
```hcl
# infrastructure/terraform/main.tf
terraform {
  required_version = ">= 1.0"

  backend "s3" {
    bucket = "afwd-terraform-state"
    key    = "prod/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = "us-east-1"
}

module "vpc" {
  source = "./modules/vpc"

  cidr_block = "10.0.0.0/16"
  environment = "production"
}

module "ecs" {
  source = "./modules/ecs"

  vpc_id = module.vpc.vpc_id
  subnets = module.vpc.private_subnets

  frontend_image = "${aws_ecr_repository.frontend.repository_url}:latest"
  backend_image = "${aws_ecr_repository.backend.repository_url}:latest"

  frontend_count = 3
  backend_count = 3
}

module "rds" {
  source = "./modules/rds"

  vpc_id = module.vpc.vpc_id
  subnets = module.vpc.database_subnets

  instance_class = "db.r6g.large"
  allocated_storage = 100
  multi_az = true
}

module "elasticache" {
  source = "./modules/elasticache"

  vpc_id = module.vpc.vpc_id
  subnets = module.vpc.cache_subnets

  node_type = "cache.r6g.large"
  num_cache_nodes = 3
}
```

### ECS Task Definitions

#### Frontend Task Definition
```json
{
  "family": "afwd-frontend",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "containerDefinitions": [
    {
      "name": "frontend",
      "image": "your-account.dkr.ecr.us-east-1.amazonaws.com/afwd-frontend:latest",
      "portMappings": [
        {
          "containerPort": 3000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "NODE_ENV",
          "value": "production"
        },
        {
          "name": "NEXT_PUBLIC_API_URL",
          "value": "https://api.afinewinedynasty.com"
        }
      ],
      "secrets": [
        {
          "name": "NEXT_PUBLIC_GOOGLE_CLIENT_ID",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:xxx:secret:google-client-id"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/afwd-frontend",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:3000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      }
    }
  ]
}
```

#### Backend Task Definition
```json
{
  "family": "afwd-backend",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "2048",
  "memory": "4096",
  "containerDefinitions": [
    {
      "name": "backend",
      "image": "your-account.dkr.ecr.us-east-1.amazonaws.com/afwd-backend:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "ENV",
          "value": "production"
        },
        {
          "name": "POSTGRES_SERVER",
          "value": "afwd-prod.cluster-xxx.us-east-1.rds.amazonaws.com"
        },
        {
          "name": "REDIS_HOST",
          "value": "afwd-prod.xxx.cache.amazonaws.com"
        }
      ],
      "secrets": [
        {
          "name": "POSTGRES_PASSWORD",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:xxx:secret:rds-password"
        },
        {
          "name": "SECRET_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:xxx:secret:jwt-secret"
        },
        {
          "name": "STRIPE_SECRET_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:xxx:secret:stripe-secret"
        }
      ],
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      }
    }
  ]
}
```

## Environment Configuration

### Production Environment Variables

#### Critical Secrets (Store in AWS Secrets Manager)
```yaml
Database:
  - POSTGRES_PASSWORD
  - DATABASE_ENCRYPTION_KEY

Authentication:
  - SECRET_KEY (JWT)
  - GOOGLE_CLIENT_SECRET
  - OAUTH_STATE_SECRET

Payments:
  - STRIPE_SECRET_KEY
  - STRIPE_WEBHOOK_SECRET

Email:
  - SENDGRID_API_KEY

External APIs:
  - MLB_API_KEY
  - FANTRAX_API_KEY
```

#### Non-Secret Configuration
```env
# Application
ENV=production
DEBUG=false
LOG_LEVEL=info

# Database
POSTGRES_SERVER=afwd-prod.cluster-xxx.us-east-1.rds.amazonaws.com
POSTGRES_DB=afinewinedynasty
POSTGRES_USER=afwd_app
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40

# Redis
REDIS_HOST=afwd-prod.xxx.cache.amazonaws.com
REDIS_PORT=6379
REDIS_DB=0
REDIS_TTL=3600

# API Configuration
API_V1_STR=/api/v1
CORS_ORIGINS=["https://afinewinedynasty.com","https://www.afinewinedynasty.com"]

# Rate Limiting
DEFAULT_RATE_LIMIT=100
PRO_RATE_LIMIT=500
PREMIUM_RATE_LIMIT=1000
```

## Database Setup

### RDS PostgreSQL Configuration
```sql
-- Create production database
CREATE DATABASE afinewinedynasty_prod;

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Create application user
CREATE USER afwd_app WITH ENCRYPTED PASSWORD 'secure_password';
GRANT CONNECT ON DATABASE afinewinedynasty_prod TO afwd_app;
GRANT USAGE ON SCHEMA public TO afwd_app;
GRANT CREATE ON SCHEMA public TO afwd_app;

-- Create read-only user for analytics
CREATE USER afwd_readonly WITH ENCRYPTED PASSWORD 'readonly_password';
GRANT CONNECT ON DATABASE afinewinedynasty_prod TO afwd_readonly;
GRANT USAGE ON SCHEMA public TO afwd_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO afwd_readonly;
```

### Database Migration Strategy
```bash
# Run migrations via CI/CD pipeline
alembic upgrade head

# Or run manually
kubectl exec -it backend-pod -- alembic upgrade head

# Verify migration
alembic current
```

## Application Deployment

### CI/CD Pipeline (GitHub Actions)
```yaml
# .github/workflows/deploy-production.yml
name: Deploy to Production

on:
  push:
    tags:
      - 'v*'

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production

    steps:
      - uses: actions/checkout@v3

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1

      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v1

      - name: Build and push Frontend
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          IMAGE_TAG: ${{ github.ref_name }}
        run: |
          docker build -f apps/web/Dockerfile -t $ECR_REGISTRY/afwd-frontend:$IMAGE_TAG apps/web
          docker push $ECR_REGISTRY/afwd-frontend:$IMAGE_TAG
          docker tag $ECR_REGISTRY/afwd-frontend:$IMAGE_TAG $ECR_REGISTRY/afwd-frontend:latest
          docker push $ECR_REGISTRY/afwd-frontend:latest

      - name: Build and push Backend
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          IMAGE_TAG: ${{ github.ref_name }}
        run: |
          docker build -f apps/api/Dockerfile -t $ECR_REGISTRY/afwd-backend:$IMAGE_TAG apps/api
          docker push $ECR_REGISTRY/afwd-backend:$IMAGE_TAG
          docker tag $ECR_REGISTRY/afwd-backend:$IMAGE_TAG $ECR_REGISTRY/afwd-backend:latest
          docker push $ECR_REGISTRY/afwd-backend:latest

      - name: Update ECS services
        run: |
          aws ecs update-service --cluster afwd-prod --service afwd-frontend --force-new-deployment
          aws ecs update-service --cluster afwd-prod --service afwd-backend --force-new-deployment

      - name: Wait for deployment
        run: |
          aws ecs wait services-stable --cluster afwd-prod --services afwd-frontend afwd-backend
```

### Deployment Checklist
- [ ] All tests passing
- [ ] Security scan completed
- [ ] Database migrations tested in staging
- [ ] Environment variables verified
- [ ] SSL certificates valid
- [ ] Monitoring alerts configured
- [ ] Backup verified
- [ ] Rollback plan documented
- [ ] Team notified

## SSL/TLS Configuration

### CloudFlare Setup
1. Add domain to CloudFlare
2. Update nameservers at registrar
3. Configure SSL/TLS mode: Full (strict)
4. Enable automatic HTTPS rewrites
5. Configure Page Rules for caching

### AWS Certificate Manager
```bash
# Request certificate
aws acm request-certificate \
  --domain-name afinewinedynasty.com \
  --subject-alternative-names "*.afinewinedynasty.com" \
  --validation-method DNS

# Attach to ALB
aws elbv2 create-listener \
  --load-balancer-arn <alb-arn> \
  --protocol HTTPS \
  --port 443 \
  --certificates CertificateArn=<cert-arn> \
  --default-actions Type=forward,TargetGroupArn=<target-group-arn>
```

## Monitoring Setup

### CloudWatch Dashboards
```json
{
  "name": "AFWD-Production-Dashboard",
  "widgets": [
    {
      "type": "metric",
      "title": "API Response Time",
      "metrics": [
        ["AWS/ECS", "CPUUtilization", {"stat": "Average"}],
        ["AWS/ECS", "MemoryUtilization", {"stat": "Average"}],
        ["AWS/ApplicationELB", "TargetResponseTime", {"stat": "Average"}]
      ]
    },
    {
      "type": "metric",
      "title": "Error Rates",
      "metrics": [
        ["AWS/ApplicationELB", "HTTPCode_Target_4XX_Count", {"stat": "Sum"}],
        ["AWS/ApplicationELB", "HTTPCode_Target_5XX_Count", {"stat": "Sum"}]
      ]
    }
  ]
}
```

### Alarms Configuration
```bash
# High CPU usage
aws cloudwatch put-metric-alarm \
  --alarm-name afwd-high-cpu \
  --alarm-description "Alert when CPU exceeds 80%" \
  --metric-name CPUUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold

# High error rate
aws cloudwatch put-metric-alarm \
  --alarm-name afwd-high-error-rate \
  --alarm-description "Alert when 5xx errors exceed 1%" \
  --metric-name HTTPCode_Target_5XX_Count \
  --namespace AWS/ApplicationELB \
  --statistic Sum \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold
```

## Backup Strategy

### Database Backups
```yaml
RDS Automated Backups:
  - Retention: 30 days
  - Backup Window: 03:00-04:00 UTC
  - Multi-AZ: Enabled

Manual Snapshots:
  - Frequency: Weekly
  - Retention: 90 days
  - Cross-region copy: Yes (us-west-2)

Point-in-Time Recovery:
  - Available for last 30 days
  - Recovery time: ~15 minutes
```

### Application Data Backup
```bash
# Backup script (run via cron)
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)

# Backup database
pg_dump $DATABASE_URL | gzip > backup_${DATE}.sql.gz

# Upload to S3
aws s3 cp backup_${DATE}.sql.gz s3://afwd-backups/database/

# Backup uploaded files
aws s3 sync /app/uploads s3://afwd-backups/uploads/${DATE}/

# Clean old backups (keep 30 days)
find /backups -mtime +30 -delete
```

## Scaling Considerations

### Horizontal Scaling
```yaml
Frontend:
  Min Tasks: 2
  Max Tasks: 10
  Target CPU: 70%
  Target Memory: 80%

Backend:
  Min Tasks: 3
  Max Tasks: 20
  Target CPU: 60%
  Target Memory: 70%

Database:
  Read Replicas: 2
  Connection Pool: 100 per instance

Redis:
  Cluster Mode: Enabled
  Shards: 3
  Replicas per Shard: 2
```

### Auto-scaling Policies
```json
{
  "ServiceName": "afwd-backend",
  "ScalableDimension": "ecs:service:DesiredCount",
  "PolicyType": "TargetTrackingScaling",
  "TargetTrackingScalingPolicyConfiguration": {
    "TargetValue": 70.0,
    "PredefinedMetricSpecification": {
      "PredefinedMetricType": "ECSServiceAverageCPUUtilization"
    },
    "ScaleOutCooldown": 60,
    "ScaleInCooldown": 300
  }
}
```

## Rollback Procedures

### Quick Rollback (< 5 minutes)
```bash
# Rollback ECS service to previous task definition
aws ecs update-service \
  --cluster afwd-prod \
  --service afwd-backend \
  --task-definition afwd-backend:previous-revision

# Verify rollback
aws ecs describe-services \
  --cluster afwd-prod \
  --services afwd-backend
```

### Database Rollback
```bash
# For recent changes (< 30 minutes)
alembic downgrade -1

# For major issues - restore from snapshot
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier afwd-prod-restored \
  --db-snapshot-identifier afwd-prod-snapshot-20240101
```

### Full Environment Rollback
1. **Notify team** via Slack/PagerDuty
2. **Switch traffic** to maintenance page
3. **Rollback services** to previous versions
4. **Restore database** if needed
5. **Clear caches** (Redis, CDN)
6. **Verify functionality** with smoke tests
7. **Switch traffic back** to application
8. **Post-mortem** within 24 hours

## Health Checks

### Endpoint Monitoring
```bash
# Production health checks
curl https://api.afinewinedynasty.com/health
curl https://afinewinedynasty.com/api/health

# Detailed health check
curl https://api.afinewinedynasty.com/health/detailed
```

### Smoke Tests
```python
# scripts/smoke_test.py
import requests
import sys

def test_production():
    endpoints = [
        "https://afinewinedynasty.com",
        "https://api.afinewinedynasty.com/health",
        "https://api.afinewinedynasty.com/api/v1/prospects"
    ]

    for endpoint in endpoints:
        response = requests.get(endpoint, timeout=10)
        assert response.status_code == 200, f"Failed: {endpoint}"
        print(f"✓ {endpoint}")

    print("All smoke tests passed!")

if __name__ == "__main__":
    test_production()
```

## Security Checklist

- [ ] All secrets in AWS Secrets Manager
- [ ] Database encrypted at rest
- [ ] SSL/TLS enforced
- [ ] Security groups properly configured
- [ ] WAF rules enabled
- [ ] DDoS protection active
- [ ] Access logs enabled
- [ ] Audit trail configured
- [ ] Vulnerability scanning scheduled
- [ ] Incident response plan documented

---

*Last updated: October 2024*
*Next review: January 2025*