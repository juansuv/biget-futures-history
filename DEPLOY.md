# Deployment Guide

## Unified Deployment Script

All previous deployment scripts have been consolidated into a single, consistent deployment script: `deploy.sh`

### Features

✅ **Proper dependency installation** for all Lambda functions  
✅ **CloudWatch logs** enabled and configured  
✅ **Interactive log watching** with `./deploy.sh watchlog`  
✅ **Clean source directory** (dependencies only in `.aws-sam/`)  
✅ **SAM-based builds** for reliability  
✅ **Automatic stack cleanup** before deployment  

### Prerequisites

1. Install SAM CLI:
   ```bash
   pip install aws-sam-cli
   ```

2. Configure AWS CLI:
   ```bash
   aws configure
   ```

### Usage

#### Deploy the application:
```bash
./deploy.sh
```

#### Watch logs interactively:
```bash
./deploy.sh watchlog
```

#### Watch specific logs:
```bash
# Watch coordinator logs
aws logs tail '/aws/lambda/bitget-coordinator' --follow

# Watch symbol processor logs  
aws logs tail '/aws/lambda/bitget-symbol-processor' --follow

# Watch result collector logs
aws logs tail '/aws/lambda/bitget-result-collector' --follow

# Watch FastAPI logs
aws logs tail '/aws/lambda/bitget-fastapi' --follow
```

### What gets deployed

- **FastAPI Lambda** with Mangum adapter
- **API Gateway** with logging enabled
- **4 Lambda functions**: coordinator, symbol processor, result collector, FastAPI
- **Step Function** with parallel processing (MaxConcurrency=50)
- **CloudWatch Log Groups** for all components

### Template used

The script uses `template_complete.yaml` which includes:
- All Lambda functions with proper IAM roles
- Step Functions for orchestration
- API Gateway with full integration
- CloudWatch logging configuration

### Stack name

The deployment creates a stack named: `bitget-api`

### Removed scripts

The following redundant scripts have been removed:
- `deploy_minimal.sh`
- `deploy_complete.sh` 
- `deploy_clean.sh`
- `deploy_complete_clean.sh`
- `deploy_simple_clean.sh`

### Dependency management

- Dependencies are installed in `.aws-sam/build/` during build
- Source code remains clean (no dependencies mixed with source)
- Each Lambda gets its dependencies from its respective `requirements.txt`

### CloudWatch Logs

All logs are automatically configured and accessible via:
- AWS Console CloudWatch Logs
- AWS CLI with `aws logs tail` commands
- Interactive log viewer: `./deploy.sh watchlog`

### Troubleshooting

If deployment fails:
1. Check AWS credentials: `aws sts get-caller-identity`
2. Ensure SAM CLI is installed: `sam --version`
3. Check CloudFormation events in AWS Console
4. View deployment logs for specific error messages