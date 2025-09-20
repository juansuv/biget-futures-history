#!/bin/bash

echo "🚀 Redeploying Bitget system with fixed dependencies..."

# Delete existing stack first
echo "🗑️  Deleting existing stack..."
aws cloudformation delete-stack --stack-name bitget-minimal

echo "⏳ Waiting for stack deletion..."
aws cloudformation wait stack-delete-complete --stack-name bitget-minimal

if [ $? -eq 0 ]; then
    echo "✅ Stack deleted successfully"
else
    echo "⚠️  Stack deletion may have issues, continuing..."
fi

# Clean any previous builds
echo "🧹 Cleaning previous builds..."
rm -rf .aws-sam/

# Install dependencies locally for each Lambda
echo "📦 Installing dependencies for each Lambda..."

# Coordinator dependencies
cd src/lambdas/coordinator
pip install -r requirements.txt -t .
cd ../../..

# Symbol processor dependencies  
cd src/lambdas/symbol_processor
pip install -r requirements.txt -t .
cd ../../..

# Result collector (no external dependencies)
echo "✅ Dependencies installed"

# Build with SAM
echo "🔨 Building SAM application..."
sam build --template-file template_minimal.yaml

if [ $? -ne 0 ]; then
    echo "❌ Build failed!"
    exit 1
fi

# Deploy
echo "🚀 Deploying to AWS..."
sam deploy \
    --template-file template_minimal.yaml \
    --stack-name bitget-minimal-v2 \
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
    echo "📊 Getting new stack outputs..."
    aws cloudformation describe-stacks \
        --stack-name bitget-minimal-v2 \
        --query 'Stacks[0].Outputs' \
        --output table
    
    echo ""
    echo "🧪 Testing new deployment..."
    
    # Test symbol processor
    aws lambda invoke \
        --function-name bitget-symbol-processor \
        --payload '{"symbol":"BTCUSDT"}' \
        test_response.json
    
    echo "Test result:"
    cat test_response.json
    
    rm -f test_response.json
    
    echo ""
    echo "🎯 New ARNs:"
    
    STEP_FUNCTION_ARN=$(aws cloudformation describe-stacks \
        --stack-name bitget-minimal-v2 \
        --query 'Stacks[0].Outputs[?OutputKey==`StepFunctionArn`].OutputValue' \
        --output text)
    
    echo "Step Function ARN: $STEP_FUNCTION_ARN"
    
    echo ""
    echo "🚀 Ready to execute Step Function:"
    echo "aws stepfunctions start-execution \\"
    echo "  --state-machine-arn '$STEP_FUNCTION_ARN' \\"
    echo "  --input '{\"symbols\":[\"BTCUSDT\",\"ETHUSDT\",\"ADAUSDT\"]}'"
    
else
    echo "❌ Deployment failed!"
    exit 1
fi

# Clean up dependencies from source
echo ""
echo "🧹 Cleaning up source directories..."
find src/lambdas -name "*.egg-info" -type d -exec rm -rf {} + 2>/dev/null
find src/lambdas -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
find src/lambdas -name "*.pyc" -delete 2>/dev/null

echo "✅ Redeploy completed!"