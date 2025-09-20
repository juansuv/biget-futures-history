#!/bin/bash

echo "🚀 Clean Deployment - Bitget API with FastAPI + Lambda + API Gateway"
echo "Dependencies will be installed in .aws-sam/ keeping source clean"
echo "=================================================================="

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

# Clean any existing builds and dependencies in source
echo "🧹 Cleaning repository..."
rm -rf .aws-sam/

# Remove any dependencies that might be in source (keep source clean)
find src -name "*.egg-info" -type d -exec rm -rf {} + 2>/dev/null
find src -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
find src -name "*.pyc" -delete 2>/dev/null
find src -name "*.dist-info" -type d -exec rm -rf {} + 2>/dev/null
find src -name "*.so" -delete 2>/dev/null
find src -type d -name "bin" -exec rm -rf {} + 2>/dev/null

# Remove known dependency directories from source
find src -maxdepth 3 -type d \( -name "aiohttp*" -o -name "requests*" -o -name "urllib3*" \
    -o -name "certifi*" -o -name "charset_normalizer*" -o -name "idna*" \
    -o -name "pybitget*" -o -name "websockets*" -o -name "loguru*" \
    -o -name "boto3*" -o -name "botocore*" -o -name "jmespath*" \
    -o -name "s3transfer*" -o -name "python_dateutil*" -o -name "six*" \
    -o -name "dateutil*" -o -name "fastapi*" -o -name "mangum*" \
    -o -name "pydantic*" -o -name "starlette*" -o -name "typing_extensions*" \
    -o -name "annotated_types*" -o -name "pydantic_core*" -o -name "anyio*" \
    -o -name "sniffio*" -o -name "click*" \) -exec rm -rf {} + 2>/dev/null

echo "✅ Repository cleaned"

# Delete existing stacks if they exist
echo "🗑️  Checking for existing stacks..."
for stack in bitget-minimal bitget-minimal-v2 bitget-complete-api; do
    aws cloudformation describe-stacks --stack-name $stack &>/dev/null
    if [ $? -eq 0 ]; then
        echo "Deleting existing stack: $stack"
        aws cloudformation delete-stack --stack-name $stack
        echo "Waiting for stack deletion..."
        aws cloudformation wait stack-delete-complete --stack-name $stack
    fi
done

# Build with SAM (this will install dependencies in .aws-sam/)
echo "🔨 Building SAM application..."
echo "SAM will install all dependencies in .aws-sam/ keeping source clean"

sam build \
    --template-file template_complete.yaml \
    --use-container

if [ $? -ne 0 ]; then
    echo "❌ Build failed!"
    echo "Trying without container..."
    sam build --template-file template_complete.yaml
    if [ $? -ne 0 ]; then
        echo "❌ Build failed again!"
        exit 1
    fi
fi

echo "✅ Build completed - all dependencies are in .aws-sam/"

# Verify source is still clean
echo "🔍 Verifying source directory is clean..."
if find src -name "*.egg-info" -o -name "aiohttp*" -o -name "pybitget*" -o -name "fastapi*" | grep -q .; then
    echo "⚠️  Warning: Some dependencies might still be in source"
else
    echo "✅ Source directory is clean"
fi

# Deploy
echo "🚀 Deploying to AWS..."
sam deploy \
    --template-file template_complete.yaml \
    --stack-name bitget-clean-api \
    --region us-east-1 \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides \
        BitgetApiKey="bg_680026a00a63d58058c738c952ce67a2" \
        BitgetSecretKey="7abac4a9404e82830db5f9db5e867a8370c7e59dc74e52615c59552d0afbd7c9" \
        BitgetPassphrase="22Dominic22" \
    --no-confirm-changeset

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 DEPLOYMENT SUCCESSFUL!"
    echo "========================"
    
    echo ""
    echo "📊 Getting stack outputs..."
    aws cloudformation describe-stacks \
        --stack-name bitget-clean-api \
        --query 'Stacks[0].Outputs' \
        --output table
    
    echo ""
    echo "🌐 Getting API Gateway URL..."
    API_URL=$(aws cloudformation describe-stacks \
        --stack-name bitget-clean-api \
        --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue' \
        --output text)
    
    STEP_FUNCTION_ARN=$(aws cloudformation describe-stacks \
        --stack-name bitget-clean-api \
        --query 'Stacks[0].Outputs[?OutputKey==`StepFunctionArn`].OutputValue' \
        --output text)
    
    echo ""
    echo "🌐 API Gateway URL: $API_URL"
    echo "📖 Documentation: ${API_URL}docs"
    echo "🏠 Landing Page: $API_URL"
    echo ""
    echo "🧪 Quick Test Commands:"
    echo "# Health check"
    echo "curl $API_URL/health"
    echo ""
    echo "# Get available symbols"
    echo "curl $API_URL/get-symbols"
    echo ""
    echo "# Extract single symbol"
    echo "curl -X POST $API_URL/extract-single-symbol \\"
    echo "  -H 'Content-Type: application/json' \\"
    echo "  -d '{\"symbol\":\"BTCUSDT\"}'"
    echo ""
    echo "# Extract multiple symbols with Step Function"
    echo "curl -X POST $API_URL/extract-orders \\"
    echo "  -H 'Content-Type: application/json' \\"
    echo "  -d '{\"symbols\":[\"BTCUSDT\",\"ETHUSDT\",\"ADAUSDT\"]}'"
    echo ""
    echo "🧪 Test with Python script:"
    echo "python test_complete_api.py $API_URL"
    echo ""
    echo "🔗 Direct URLs:"
    echo "• 🏠 Home: $API_URL"
    echo "• 📖 Docs: ${API_URL}docs"
    echo "• ❤️  Health: ${API_URL}health"
    echo "• 📋 Symbols: ${API_URL}get-symbols"
    echo ""
    echo "📋 Infrastructure ARNs:"
    echo "• Step Function: $STEP_FUNCTION_ARN"
    
    # Verify source is still clean after deployment
    echo ""
    echo "🔍 Final verification - source directory status:"
    if find src -name "*.egg-info" -o -name "aiohttp*" -o -name "pybitget*" -o -name "fastapi*" | grep -q .; then
        echo "⚠️  Some dependencies found in source (will be ignored by git)"
    else
        echo "✅ Source directory remains clean"
    fi
    
    echo ""
    echo "📁 All dependencies are contained in:"
    echo "   .aws-sam/build/   (ignored by git)"
    echo ""
    echo "✅ Clean deployment completed successfully!"
        
else
    echo "❌ Deployment failed!"
    exit 1
fi

echo ""
echo "🎯 What's deployed:"
echo "• ✅ FastAPI app with Mangum adapter"
echo "• ✅ API Gateway with custom domain"
echo "• ✅ 4 Lambda functions (coordinator, processor, collector, api)"
echo "• ✅ Step Function with parallel processing (MaxConcurrency=50)"
echo "• ✅ Complete web interface with docs"
echo "• ✅ Clean source code (dependencies only in .aws-sam/)"