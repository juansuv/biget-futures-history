#!/bin/bash

# Bitget Trading Orders - Minimal Deployment
echo "🚀 Deploying Bitget Trading Orders (Minimal - Lambda Only)..."

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

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf .aws-sam/

# Build with minimal template
echo "📦 Building SAM application (minimal)..."
sam build --template-file template_minimal.yaml

if [ $? -ne 0 ]; then
    echo "❌ Build failed!"
    exit 1
fi

# Deploy
echo "🚀 Deploying to AWS..."
sam deploy \
    --template-file template_minimal.yaml \
    --stack-name bitget-minimal \
    --region us-east-1 \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides \
        BitgetApiKey="bg_680026a00a63d58058c738c952ce67a2" \
        BitgetSecretKey="7abac4a9404e82830db5f9db5e867a8370c7e59dc74e52615c59552d0afbd7c9" \
        BitgetPassphrase="22Dominic22" \
    --no-confirm-changeset

if [ $? -eq 0 ]; then
    echo "✅ Deployment completed successfully!"
    echo ""
    echo "📊 Getting stack outputs..."
    aws cloudformation describe-stacks \
        --stack-name bitget-minimal \
        --query 'Stacks[0].Outputs' \
        --output table
    
    echo ""
    echo "🎯 Key ARNs:"
    
    echo "Step Function ARN:"
    STEP_FUNCTION_ARN=$(aws cloudformation describe-stacks \
        --stack-name bitget-minimal \
        --query 'Stacks[0].Outputs[?OutputKey==`StepFunctionArn`].OutputValue' \
        --output text)
    echo "$STEP_FUNCTION_ARN"
    
    echo ""
    echo "Symbol Processor Lambda ARN:"
    SYMBOL_PROCESSOR_ARN=$(aws cloudformation describe-stacks \
        --stack-name bitget-minimal \
        --query 'Stacks[0].Outputs[?OutputKey==`SymbolProcessorFunctionArn`].OutputValue' \
        --output text)
    echo "$SYMBOL_PROCESSOR_ARN"
    
    echo ""
    echo "🧪 Test commands:"
    echo "# Test coordinator directly:"
    echo "aws lambda invoke --function-name bitget-coordinator --payload '{}' response.json"
    echo ""
    echo "# Test symbol processor:"
    echo "aws lambda invoke --function-name bitget-symbol-processor --payload '{\"symbol\":\"BTCUSDT\"}' response.json"
    echo ""
    echo "# Start Step Function:"
    echo "aws stepfunctions start-execution --state-machine-arn $STEP_FUNCTION_ARN --input '{\"symbols\":[\"BTCUSDT\",\"ETHUSDT\"]}'"
        
else
    echo "❌ Deployment failed!"
    exit 1
fi