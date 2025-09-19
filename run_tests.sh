#!/bin/bash

# Script para ejecutar todos los tests del servicio Bitget

echo "🚀 Bitget API Test Suite"
echo "========================"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "   Run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

echo "✅ Virtual environment activated"

# Check if server is running
echo "🔍 Checking if server is running..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Server is running at http://localhost:8000"
    SERVER_RUNNING=true
else
    echo "⚠️  Server not running. Starting server..."
    SERVER_RUNNING=false
    
    # Start server in background
    python main.py &
    SERVER_PID=$!
    
    # Wait for server to start
    echo "⏳ Waiting for server to start..."
    for i in {1..10}; do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            echo "✅ Server started successfully"
            SERVER_RUNNING=true
            break
        fi
        sleep 1
    done
    
    if [ "$SERVER_RUNNING" = false ]; then
        echo "❌ Failed to start server"
        exit 1
    fi
fi

echo ""

# Function to run test with error handling
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    echo "🧪 Running: $test_name"
    echo "   Command: $test_command"
    echo "   ---"
    
    if eval "$test_command"; then
        echo "   ✅ $test_name completed successfully"
    else
        echo "   ❌ $test_name failed"
        return 1
    fi
    echo ""
}

# Test menu
echo "Select test to run:"
echo "1) Basic API Test (demo_simple.py)"
echo "2) Local Server Test (3 cycles)"
echo "3) Stress Test (50 requests per endpoint)"
echo "4) All Tests (sequential)"
echo "5) Custom Test Parameters"
echo ""
read -p "Enter your choice (1-5): " choice

case $choice in
    1)
        echo "🔥 Running Basic API Test..."
        run_test "Basic API Test" "python demo_simple.py"
        ;;
    2)
        echo "🔥 Running Local Server Test..."
        run_test "Local Server Test" "python test_server_local.py --cycles 3 --delay 2"
        ;;
    3)
        echo "🔥 Running Stress Test..."
        run_test "Stress Test" "python stress_test_endpoints.py --requests 50 --concurrent 10"
        ;;
    4)
        echo "🔥 Running All Tests..."
        run_test "Basic API Test" "python demo_simple.py"
        run_test "Local Server Test" "python test_server_local.py --cycles 2 --delay 1"
        run_test "Stress Test" "python stress_test_endpoints.py --requests 30 --concurrent 5"
        ;;
    5)
        echo "Custom Test Parameters:"
        read -p "Enter number of cycles for server test (default: 3): " cycles
        read -p "Enter delay between calls in seconds (default: 2): " delay
        read -p "Enter number of requests per endpoint for stress test (default: 50): " requests
        read -p "Enter max concurrent requests (default: 10): " concurrent
        
        cycles=${cycles:-3}
        delay=${delay:-2}
        requests=${requests:-50}
        concurrent=${concurrent:-10}
        
        echo "🔥 Running Custom Tests..."
        run_test "Custom Server Test" "python test_server_local.py --cycles $cycles --delay $delay"
        run_test "Custom Stress Test" "python stress_test_endpoints.py --requests $requests --concurrent $concurrent"
        ;;
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac

# Clean up if we started the server
if [ "$SERVER_RUNNING" = false ] && [ ! -z "$SERVER_PID" ]; then
    echo "🛑 Stopping server (PID: $SERVER_PID)..."
    kill $SERVER_PID 2>/dev/null
    echo "✅ Server stopped"
fi

echo ""
echo "🎉 Test execution completed!"
echo "📁 Check for result files: test_results_*.json and stress_test_results_*.json"