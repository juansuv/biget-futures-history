#!/bin/bash

echo "🚀 Deploying Complete Bitget API with FastAPI + Lambda + API Gateway..."

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

# Delete existing minimal stack if exists
echo "🗑️  Checking for existing stacks..."
aws cloudformation describe-stacks --stack-name bitget-minimal &>/dev/null
if [ $? -eq 0 ]; then
    echo "Deleting existing minimal stack..."
    aws cloudformation delete-stack --stack-name bitget-minimal
    aws cloudformation wait stack-delete-complete --stack-name bitget-minimal
fi

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf .aws-sam/

# Install dependencies locally for each Lambda
echo "📦 Installing dependencies for each Lambda..."

# Create virtual environment for dependency installation
python3 -m venv temp_venv
source temp_venv/bin/activate

# Coordinator dependencies
echo "Installing coordinator dependencies..."
pip install -r src/lambdas/coordinator/requirements.txt -t src/lambdas/coordinator/ --upgrade

# Symbol processor dependencies  
echo "Installing symbol processor dependencies..."
pip install -r src/lambdas/symbol_processor/requirements.txt -t src/lambdas/symbol_processor/ --upgrade

# FastAPI dependencies
echo "Installing FastAPI dependencies..."
pip install -r src/api/requirements.txt -t src/api/ --upgrade

# Deactivate and remove temp venv
deactivate
rm -rf temp_venv

echo "✅ Dependencies installed"

# Build with SAM
echo "🔨 Building SAM application..."
sam build --template-file template_complete.yaml

if [ $? -ne 0 ]; then
    echo "❌ Build failed!"
    exit 1
fi

# Deploy
echo "🚀 Deploying to AWS..."
sam deploy \
    --template-file template_complete.yaml \
    --stack-name bitget-complete-api \
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
        --stack-name bitget-complete-api \
        --query 'Stacks[0].Outputs' \
        --output table
    
    echo ""
    echo "🌐 Getting API Gateway URL..."
    API_URL=$(aws cloudformation describe-stacks \
        --stack-name bitget-complete-api \
        --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue' \
        --output text)
    
    STEP_FUNCTION_ARN=$(aws cloudformation describe-stacks \
        --stack-name bitget-complete-api \
        --query 'Stacks[0].Outputs[?OutputKey==`StepFunctionArn`].OutputValue' \
        --output text)
    
    echo ""
    echo "🎉 DEPLOYMENT SUCCESSFUL!"
    echo "========================"
    echo ""
    echo "🌐 API Gateway URL: $API_URL"
    echo "📖 Documentation: ${API_URL}docs"
    echo "🏠 Landing Page: $API_URL"
    echo ""
    echo "🧪 Test Commands:"
    echo "# Health check"
    echo "curl $API_URL/health"
    echo ""
    echo "# Get available symbols"
    echo "curl $API_URL/get-symbols"
    echo ""
    echo "# Extract orders from specific symbol"
    echo "curl -X POST $API_URL/extract-single-symbol \\"
    echo "  -H 'Content-Type: application/json' \\"
    echo "  -d '{\"symbol\":\"BTCUSDT\"}'"
    echo ""
    echo "# Extract orders using Step Function (multiple symbols)"
    echo "curl -X POST $API_URL/extract-orders \\"
    echo "  -H 'Content-Type: application/json' \\"
    echo "  -d '{\"symbols\":[\"BTCUSDT\",\"ETHUSDT\",\"ADAUSDT\"]}'"
    echo ""
    echo "🔗 Useful URLs:"
    echo "• Landing page: $API_URL"
    echo "• Health check: ${API_URL}health"
    echo "• API docs: ${API_URL}docs"
    echo "• Get symbols: ${API_URL}get-symbols"
    echo ""
    echo "📋 Step Function ARN: $STEP_FUNCTION_ARN"
        
else
    echo "❌ Deployment failed!"
    exit 1
fi

# Clean up dependencies from source
echo ""
echo "🧹 Cleaning up source directories..."
find src -name "*.egg-info" -type d -exec rm -rf {} + 2>/dev/null
find src -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
find src -name "*.pyc" -delete 2>/dev/null
find src -name "*.dist-info" -type d -exec rm -rf {} + 2>/dev/null

echo "✅ Complete API deployment finished!"
echo ""
echo "🎯 Next steps:"
echo "1. Visit $API_URL to see the landing page"
echo "2. Visit ${API_URL}docs for interactive API documentation"
echo "3. Use the curl commands above to test the API"