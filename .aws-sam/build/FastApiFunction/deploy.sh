#!/bin/bash

# Bitget Trading Orders Deployment Script
echo "🚀 Deploying Bitget Trading Orders Application..."

# Check if SAM CLI is installed
if ! command -v sam &> /dev/null; then
    echo "❌ SAM CLI is not installed. Please install it first:"
    echo "   pip install aws-sam-cli"
    exit 1
fi

# Check if AWS CLI is configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS CLI is not configured. Please run 'aws configure' first."
    exit 1
fi

# Build the application
echo "📦 Building SAM application..."
sam build

if [ $? -ne 0 ]; then
    echo "❌ Build failed!"
    exit 1
fi

# Deploy the application
echo "🚀 Deploying to AWS..."
sam deploy \
    --guided \
    --stack-name bitget-trading-orders \
    --region us-east-1 \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides \
        BitgetApiKey="bg_680026a00a63d58058c738c952ce67a2" \
        BitgetSecretKey="7abac4a9404e82830db5f9db5e867a8370c7e59dc74e52615c59552d0afbd7c9" \
        BitgetPassphrase="22Dominic22"

if [ $? -eq 0 ]; then
    echo "✅ Deployment completed successfully!"
    echo ""
    echo "📊 Getting stack outputs..."
    aws cloudformation describe-stacks \
        --stack-name bitget-trading-orders \
        --query 'Stacks[0].Outputs' \
        --output table
else
    echo "❌ Deployment failed!"
    exit 1
fi