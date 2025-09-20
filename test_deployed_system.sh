#!/bin/bash

# Test script for deployed Bitget system
echo "🚀 Testing Deployed Bitget System"
echo "=================================="

# Get ARNs from CloudFormation
echo "📋 Getting system ARNs..."
STEP_FUNCTION_ARN=$(aws cloudformation describe-stacks \
  --stack-name bitget-minimal \
  --query 'Stacks[0].Outputs[?OutputKey==`StepFunctionArn`].OutputValue' \
  --output text)

COORDINATOR_ARN=$(aws cloudformation describe-stacks \
  --stack-name bitget-minimal \
  --query 'Stacks[0].Outputs[?OutputKey==`CoordinatorFunctionArn`].OutputValue' \
  --output text)

SYMBOL_PROCESSOR_ARN=$(aws cloudformation describe-stacks \
  --stack-name bitget-minimal \
  --query 'Stacks[0].Outputs[?OutputKey==`SymbolProcessorFunctionArn`].OutputValue' \
  --output text)

echo "Step Function ARN: $STEP_FUNCTION_ARN"
echo "Coordinator ARN: $COORDINATOR_ARN"
echo "Symbol Processor ARN: $SYMBOL_PROCESSOR_ARN"
echo ""

# Test 1: Coordinator Lambda
echo "🧪 Test 1: Coordinator Lambda"
echo "------------------------------"
aws lambda invoke \
  --function-name bitget-coordinator \
  --payload '{"test_mode": true}' \
  response_coordinator.json

if [ $? -eq 0 ]; then
  echo "✅ Coordinator invoked successfully"
  SYMBOLS=$(cat response_coordinator.json | jq -r '.body' | jq -r '.symbols[]' | head -5 | tr '\n' ',' | sed 's/,$//')
  echo "Found symbols: $SYMBOLS"
else
  echo "❌ Coordinator failed"
fi
echo ""

# Test 2: Symbol Processor Lambda
echo "🧪 Test 2: Symbol Processor Lambda"
echo "-----------------------------------"
aws lambda invoke \
  --function-name bitget-symbol-processor \
  --payload '{"symbol":"BTCUSDT"}' \
  response_symbol.json

if [ $? -eq 0 ]; then
  echo "✅ Symbol Processor invoked successfully"
  ORDERS_COUNT=$(cat response_symbol.json | jq -r '.orders_count')
  echo "Orders found for BTCUSDT: $ORDERS_COUNT"
else
  echo "❌ Symbol Processor failed"
fi
echo ""

# Test 3: Step Function Execution
echo "🧪 Test 3: Step Function Execution"
echo "-----------------------------------"
EXECUTION_ARN=$(aws stepfunctions start-execution \
  --state-machine-arn "$STEP_FUNCTION_ARN" \
  --input '{"symbols":["BTCUSDT","ETHUSDT","ADAUSDT"]}' \
  --query 'executionArn' \
  --output text)

if [ $? -eq 0 ]; then
  echo "✅ Step Function execution started"
  echo "Execution ARN: $EXECUTION_ARN"
  
  echo "⏳ Waiting for execution to complete..."
  sleep 10
  
  # Check execution status
  STATUS=$(aws stepfunctions describe-execution \
    --execution-arn "$EXECUTION_ARN" \
    --query 'status' \
    --output text)
  
  echo "Execution Status: $STATUS"
  
  if [ "$STATUS" = "SUCCEEDED" ]; then
    echo "🎉 Step Function completed successfully!"
    
    # Get output
    OUTPUT=$(aws stepfunctions describe-execution \
      --execution-arn "$EXECUTION_ARN" \
      --query 'output' \
      --output text)
    
    echo "Results summary:"
    echo "$OUTPUT" | jq -r '.final_result.Payload.body' | jq -r '.message, .total_orders, .symbols_processed'
    
  elif [ "$STATUS" = "RUNNING" ]; then
    echo "⏳ Execution still running. Check later with:"
    echo "aws stepfunctions describe-execution --execution-arn $EXECUTION_ARN"
  else
    echo "❌ Execution failed or aborted"
  fi
else
  echo "❌ Failed to start Step Function"
fi
echo ""

# Test 4: Performance Test with Many Symbols
echo "🧪 Test 4: Performance Test (10 symbols in parallel)"
echo "----------------------------------------------------"
PERF_EXECUTION_ARN=$(aws stepfunctions start-execution \
  --state-machine-arn "$STEP_FUNCTION_ARN" \
  --input '{"symbols":["BTCUSDT","ETHUSDT","ADAUSDT","SOLUSDT","BNBUSDT","DOGEUSDT","AVAXUSDT","DOTUSDT","LINKUSDT","UNIUSDT"]}' \
  --query 'executionArn' \
  --output text)

if [ $? -eq 0 ]; then
  echo "✅ Performance test started"
  echo "Execution ARN: $PERF_EXECUTION_ARN"
  echo "This will process 10 symbols in parallel with MaxConcurrency=50"
  echo ""
  echo "Monitor with:"
  echo "aws stepfunctions describe-execution --execution-arn $PERF_EXECUTION_ARN"
else
  echo "❌ Failed to start performance test"
fi

echo ""
echo "🎯 Summary"
echo "=========="
echo "1. Individual Lambda tests completed"
echo "2. Step Function execution initiated"
echo "3. Performance test with 10 symbols started"
echo ""
echo "📊 Monitor executions:"
echo "aws stepfunctions list-executions --state-machine-arn $STEP_FUNCTION_ARN"
echo ""
echo "🔍 View CloudWatch logs:"
echo "aws logs describe-log-groups --log-group-name-prefix '/aws/lambda/bitget-'"
echo ""
echo "📋 Get final results:"
echo "aws stepfunctions describe-execution --execution-arn $EXECUTION_ARN --query 'output'"

# Clean up response files
rm -f response_*.json

echo ""
echo "✅ Testing completed!"