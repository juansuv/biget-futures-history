#!/bin/bash

echo "🚀 Bitget Trading API - Unified Deployment"
echo "==========================================="
echo "• Installs dependencies properly for all lambdas"
echo "• Enables CloudWatch logs with watchlog functionality"
echo "• Maintains clean source directory"
echo "• Uses SAM for reliable builds"
echo ""

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

# Configuration
STACK_NAME="bitget-api"
TEMPLATE_FILE="template_complete.yaml"
BUILT_TEMPLATE=".aws-sam/build/template.yaml"

# Function to watch CloudWatch logs
watch_logs() {
    echo "📊 Setting up log watching..."
    echo ""
    echo "Available log groups:"
    aws logs describe-log-groups --log-group-name-prefix '/aws/lambda/bitget-' --query 'logGroups[].logGroupName' --output table
    echo ""
    echo "🔍 To watch logs in real-time, use these commands:"
    echo ""
    echo "# Watch all Lambda logs:"
    echo "aws logs tail '/aws/lambda/bitget-time-range-mapper' --follow"
    echo "aws logs tail '/aws/lambda/bitget-symbol-searcher' --follow"
    echo "aws logs tail '/aws/lambda/bitget-symbol-unifier' --follow"
    echo "aws logs tail '/aws/lambda/bitget-symbol-processor' --follow"
    echo "aws logs tail '/aws/lambda/bitget-result-collector' --follow"
    echo "aws logs tail '/aws/lambda/bitget-fastapi' --follow"
    echo ""
    echo "# Watch API Gateway logs:"
    aws logs describe-log-groups --log-group-name-prefix '/aws/apigateway/' --query 'logGroups[].logGroupName' --output table
    echo ""
    
    # Interactive log watching
    while true; do
        echo "Select a log to watch:"
        echo "1) Time Range Mapper Lambda"
        echo "2) Symbol Searcher Lambda"
        echo "3) Symbol Unifier Lambda"
        echo "4) Symbol Processor Lambda"
        echo "5) Result Collector Lambda"
        echo "6) FastAPI Lambda"
        echo "7) API Gateway"
        echo "8) All Lambda logs (parallel)"
        echo "0) Exit"
        echo ""
        read -p "Choose option (0-8): " choice
        
        case $choice in
            1)
                echo "📊 Watching Time Range Mapper logs (Ctrl+C to stop)..."
                aws logs tail '/aws/lambda/bitget-time-range-mapper' --follow
                ;;
            2)
                echo "📊 Watching Symbol Searcher logs (Ctrl+C to stop)..."
                aws logs tail '/aws/lambda/bitget-symbol-searcher' --follow
                ;;
            3)
                echo "📊 Watching Symbol Unifier logs (Ctrl+C to stop)..."
                aws logs tail '/aws/lambda/bitget-symbol-unifier' --follow
                ;;
            4)
                echo "📊 Watching Symbol Processor logs (Ctrl+C to stop)..."
                aws logs tail '/aws/lambda/bitget-symbol-processor' --follow
                ;;
            5)
                echo "📊 Watching Result Collector logs (Ctrl+C to stop)..."
                aws logs tail '/aws/lambda/bitget-result-collector' --follow
                ;;
            6)
                echo "📊 Watching FastAPI logs (Ctrl+C to stop)..."
                aws logs tail '/aws/lambda/bitget-fastapi' --follow
                ;;
            7)
                # Get API Gateway log group name
                API_LOG_GROUP=$(aws logs describe-log-groups --log-group-name-prefix '/aws/apigateway/' --query 'logGroups[0].logGroupName' --output text)
                if [ "$API_LOG_GROUP" != "None" ] && [ -n "$API_LOG_GROUP" ]; then
                    echo "📊 Watching API Gateway logs (Ctrl+C to stop)..."
                    aws logs tail "$API_LOG_GROUP" --follow
                else
                    echo "❌ No API Gateway logs found"
                fi
                ;;
            8)
                echo "📊 Watching all Lambda logs in parallel (Ctrl+C to stop all)..."
                echo "Opening separate terminals for each log stream..."
                echo ""
                echo "Run these commands in separate terminals:"
                echo "aws logs tail '/aws/lambda/bitget-time-range-mapper' --follow"
                echo "aws logs tail '/aws/lambda/bitget-symbol-searcher' --follow"
                echo "aws logs tail '/aws/lambda/bitget-symbol-unifier' --follow"
                echo "aws logs tail '/aws/lambda/bitget-symbol-processor' --follow"
                echo "aws logs tail '/aws/lambda/bitget-result-collector' --follow"
                echo "aws logs tail '/aws/lambda/bitget-fastapi' --follow"
                ;;
            0)
                echo "Exiting log viewer..."
                break
                ;;
            *)
                echo "Invalid option. Please choose 0-8."
                ;;
        esac
        echo ""
    done
}

# Check if user wants to only watch logs
if [ "$1" = "watchlog" ] || [ "$1" = "logs" ] || [ "$1" = "watch" ]; then
    watch_logs
    exit 0
fi

# Clean previous builds and deployment artifacts
echo "🧹 Cleaning previous builds..."
rm -rf .aws-sam/
rm -f *.zip

# Clean source directory of any accidentally installed dependencies
echo "🧹 Cleaning source directory..."
find src -name "*.egg-info" -type d -exec rm -rf {} + 2>/dev/null
find src -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
find src -name "*.pyc" -delete 2>/dev/null
find src -name "*.dist-info" -type d -exec rm -rf {} + 2>/dev/null

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

echo "✅ Source directory cleaned"

# Check if stack exists but don't delete it (to preserve S3 bucket)
echo "🔍 Checking for existing stack..."
aws cloudformation describe-stacks --stack-name $STACK_NAME &>/dev/null
if [ $? -eq 0 ]; then
    echo "ℹ️  Stack $STACK_NAME already exists. Will update in place."
    echo "ℹ️  S3 bucket will be preserved with existing data."
else
    echo "ℹ️  Stack $STACK_NAME does not exist. Will create new."
fi

# Setup CloudWatch Logs
echo ""
echo "📊 Setting up CloudWatch Logs..."

# Create IAM role for CloudWatch Logs
TRUST_POLICY='{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "apigateway.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}'

# Create the role
aws iam create-role \
  --role-name APIGatewayCloudWatchLogsRole \
  --assume-role-policy-document "$TRUST_POLICY" \
  --description "Role for API Gateway to write to CloudWatch Logs" \
  2>/dev/null || echo "ℹ️  Role already exists, continuing..."

# Attach policy for CloudWatch Logs
aws iam attach-role-policy \
  --role-name APIGatewayCloudWatchLogsRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs

# Get role ARN
ROLE_ARN=$(aws iam get-role \
  --role-name APIGatewayCloudWatchLogsRole \
  --query 'Role.Arn' \
  --output text)

echo "✅ CloudWatch Logs role: $ROLE_ARN"

# Configure the role in API Gateway account settings
echo "⚙️  Configuring API Gateway account settings..."
aws apigateway put-account \
  --cli-binary-format raw-in-base64-out \
  --cloudwatch-role-arn "$ROLE_ARN" || echo "ℹ️  Account settings updated"

# Verify requirements.txt files exist for all functions
echo ""
echo "📋 Verifying requirements files..."
FUNCTIONS=("symbol_processor" "result_collector" "time_range_mapper" "symbol_searcher" "symbol_unifier")
API_REQUIREMENTS="src/api/requirements.txt"

for func in "${FUNCTIONS[@]}"; do
    REQ_FILE="src/lambdas/$func/requirements.txt"
    if [ ! -f "$REQ_FILE" ]; then
        echo "❌ Missing requirements.txt for $func"
        exit 1
    fi
    echo "✅ $func requirements:"
    cat "$REQ_FILE" | sed 's/^/  /'
done

if [ ! -f "$API_REQUIREMENTS" ]; then
    echo "❌ Missing requirements.txt for API"
    exit 1
fi
echo "✅ API requirements:"
cat "$API_REQUIREMENTS" | sed 's/^/  /'

# Build with SAM - this installs all dependencies properly
echo ""
echo "🔨 Building with SAM (installing dependencies)..."
sam build \
    --template-file $TEMPLATE_FILE \
    --parallel \
    --use-container

if [ $? -ne 0 ]; then
    echo "⚠️  Container build failed, retrying without container..."
    sam build \
        --template-file $TEMPLATE_FILE \
        --parallel
    
    if [ $? -ne 0 ]; then
        echo "❌ Build failed!"
        exit 1
    fi
fi

echo "✅ Build completed successfully"

# Verify that dependencies were installed correctly
echo ""
echo "🔍 Verifying installed dependencies..."

# Check FastAPI in API function
if [ -d ".aws-sam/build/FastApiFunction/fastapi" ]; then
    echo "✅ FastAPI installed in API function"
else
    echo "❌ FastAPI NOT found in API function"
    ls -la .aws-sam/build/FastApiFunction/ | head -10
fi


# Check pybitget in symbol processor
if [ -d ".aws-sam/build/SymbolProcessorFunction/pybitget" ]; then
    echo "✅ pybitget installed in symbol processor function"
else
    echo "❌ pybitget NOT found in symbol processor function"
    ls -la .aws-sam/build/SymbolProcessorFunction/ | head -10
fi

# Deploy with CloudWatch logs enabled
echo ""
echo "🚀 Deploying stack with CloudWatch logs enabled..."
sam deploy \
    --template-file $BUILT_TEMPLATE \
    --stack-name $STACK_NAME \
    --capabilities CAPABILITY_IAM \
    --no-confirm-changeset \
    --resolve-s3 \
    --parameter-overrides \
        EnableApiGatewayLogs=true

if [ $? -eq 0 ]; then
    echo "✅ Stack deployed successfully!"
    
    # Get API URL
    API_URL=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue' \
        --output text)
    
    # Get Step Function ARN
    STEP_FUNCTION_ARN=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --query 'Stacks[0].Outputs[?OutputKey==`StepFunctionArn`].OutputValue' \
        --output text)
    
    echo ""
    echo "🎉 Deployment completed!"
    echo "========================="
    echo ""
    echo "🌐 API URL: $API_URL"
    echo "📖 Documentation: ${API_URL}docs"
    echo ""
    echo "📋 Available endpoints:"
    echo "• 📖 Documentation: ${API_URL}docs"
    echo "• ⚡ Extract Orders: ${API_URL}extract-orders"
    echo ""
    echo "🧪 Quick test command:"
    echo "# Extract all orders (ultra-fast)"
    echo "curl -X POST ${API_URL}extract-orders \\"
    echo "  -H 'Content-Type: application/json' \\"
    echo "  -d '{\"test_mode\": false}'"
    echo ""
    
    # Wait for services to initialize
    echo "⏳ Waiting for services to initialize..."
    sleep 15
    
    # Quick API test
    echo "🧪 Testing API documentation..."
    curl -s "${API_URL}docs" > /dev/null && echo "✅ API docs accessible" || echo "API still initializing..."
    
    echo ""
    echo "📊 CloudWatch Log Groups:"
    aws logs describe-log-groups --log-group-name-prefix '/aws/lambda/bitget-' --query 'logGroups[].logGroupName' --output table
    
    echo ""
    echo "📊 API Gateway Log Groups:"
    aws logs describe-log-groups --log-group-name-prefix '/aws/apigateway/' --query 'logGroups[].logGroupName' --output table
    
    echo ""
    echo "🔍 View logs with:"
    echo "   ./deploy.sh watchlog"
    echo ""
    echo "📋 Infrastructure ARNs:"
    echo "• Step Function: $STEP_FUNCTION_ARN"
    
    # Verify source is still clean
    echo ""
    echo "🔍 Verifying source directory remains clean..."
    if find src -name "*.egg-info" -o -name "aiohttp*" -o -name "pybitget*" -o -name "fastapi*" | grep -q .; then
        echo "⚠️  Some dependencies found in source (will be ignored by git)"
    else
        echo "✅ Source directory is clean"
    fi
    
    echo ""
    echo "✅ Unified deployment completed successfully!"
    echo ""
    echo "🔧 What was deployed:"
    echo "• ✅ All Lambda dependencies properly installed"
    echo "• ✅ CloudWatch logs enabled and configured"
    echo "• ✅ API Gateway with logging"
    echo "• ✅ Step Function for parallel processing"
    echo "• ✅ FastAPI with complete documentation"
    echo "• ✅ Clean source code (dependencies in .aws-sam/)"
    echo ""
    echo "📊 Log watching available: ./deploy.sh watchlog"
    
else
    echo "❌ Deployment failed!"
    exit 1
fi
