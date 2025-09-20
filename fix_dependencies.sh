#!/bin/bash

echo "🔧 Fixing Lambda dependencies..."

# Create deployment packages with dependencies
echo "📦 Creating deployment packages..."

# Function to create deployment package
create_lambda_package() {
    local lambda_name=$1
    local lambda_dir="src/lambdas/$lambda_name"
    
    echo "Creating package for $lambda_name..."
    
    # Create temp directory
    mkdir -p "temp_$lambda_name"
    
    # Copy function code
    cp "$lambda_dir"/*.py "temp_$lambda_name/"
    
    # Install dependencies in the temp directory
    if [ -f "$lambda_dir/requirements.txt" ]; then
        pip install -r "$lambda_dir/requirements.txt" -t "temp_$lambda_name/"
    fi
    
    # Create ZIP package
    cd "temp_$lambda_name"
    zip -r "../${lambda_name}_deployment.zip" .
    cd ..
    
    # Clean up
    rm -rf "temp_$lambda_name"
    
    echo "✅ Package created: ${lambda_name}_deployment.zip"
}

# Create packages for each Lambda
create_lambda_package "coordinator"
create_lambda_package "symbol_processor" 
create_lambda_package "result_collector"

echo ""
echo "📤 Uploading Lambda functions..."

# Update each Lambda function
aws lambda update-function-code \
    --function-name bitget-coordinator \
    --zip-file fileb://coordinator_deployment.zip

aws lambda update-function-code \
    --function-name bitget-symbol-processor \
    --zip-file fileb://symbol_processor_deployment.zip

aws lambda update-function-code \
    --function-name bitget-result-collector \
    --zip-file fileb://result_collector_deployment.zip

echo ""
echo "✅ Lambda functions updated with dependencies!"

# Clean up deployment packages
rm -f *_deployment.zip

echo ""
echo "🧪 Testing updated functions..."

# Test symbol processor
aws lambda invoke \
    --function-name bitget-symbol-processor \
    --payload '{"symbol":"BTCUSDT"}' \
    test_response.json

echo "Symbol processor test result:"
cat test_response.json

rm -f test_response.json

echo ""
echo "✅ Fix completed!"