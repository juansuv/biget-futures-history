#!/bin/bash

echo "🧹 Cleaning Repository - Removing all dependencies from source"
echo "Dependencies will only exist in .aws-sam/ during builds"
echo "=========================================================="

# Remove SAM build artifacts
echo "Removing .aws-sam/ directory..."
rm -rf .aws-sam/

# Remove Python cache files
echo "Removing Python cache files..."
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null
find . -name "*.pyo" -delete 2>/dev/null

# Remove egg-info and dist-info directories
echo "Removing Python packaging artifacts..."
find src -name "*.egg-info" -type d -exec rm -rf {} + 2>/dev/null
find src -name "*.dist-info" -type d -exec rm -rf {} + 2>/dev/null

# Remove compiled extensions
echo "Removing compiled extensions..."
find src -name "*.so" -delete 2>/dev/null
find src -name "*.dylib" -delete 2>/dev/null

# Remove bin directories that pip creates
echo "Removing bin directories..."
find src -type d -name "bin" -exec rm -rf {} + 2>/dev/null

# Remove specific dependency directories from source
echo "Removing known dependency directories from source..."
find src -maxdepth 3 -type d \( \
    -name "aiohttp*" -o -name "requests*" -o -name "urllib3*" \
    -o -name "certifi*" -o -name "charset_normalizer*" -o -name "idna*" \
    -o -name "pybitget*" -o -name "websockets*" -o -name "loguru*" \
    -o -name "boto3*" -o -name "botocore*" -o -name "jmespath*" \
    -o -name "s3transfer*" -o -name "python_dateutil*" -o -name "six*" \
    -o -name "dateutil*" -o -name "fastapi*" -o -name "mangum*" \
    -o -name "pydantic*" -o -name "starlette*" -o -name "typing_extensions*" \
    -o -name "annotated_types*" -o -name "pydantic_core*" -o -name "anyio*" \
    -o -name "sniffio*" -o -name "click*" -o -name "uvloop*" \
    -o -name "h11*" -o -name "httptools*" -o -name "uvicorn*" \
    -o -name "multidict*" -o -name "yarl*" -o -name "aiosignal*" \
    -o -name "frozenlist*" -o -name "attrs*" -o -name "async_timeout*" \
\) -exec rm -rf {} + 2>/dev/null

# Remove individual dependency files that might be scattered
echo "Removing individual dependency files..."
find src -maxdepth 3 -type f \( \
    -name "*aiohttp*" -o -name "*requests*" -o -name "*urllib3*" \
    -o -name "*pybitget*" -o -name "*fastapi*" -o -name "*mangum*" \
    -o -name "*pydantic*" -o -name "*boto3*" \
\) -not -name "requirements.txt" -delete 2>/dev/null

# Remove test artifacts
echo "Removing test artifacts..."
rm -f test_results_*.json
rm -f stress_test_results_*.json
rm -f response*.json
rm -f *_deployment.zip

# Remove temporary directories
echo "Removing temporary directories..."
rm -rf temp_*/
rm -rf venv/
rm -rf .venv/

echo ""
echo "✅ Repository cleaned successfully!"
echo ""
echo "📁 Source directory structure:"
find src -type f -name "*.py" | head -10
echo ""
echo "🔍 Verifying no dependencies in source:"
if find src -name "aiohttp*" -o -name "pybitget*" -o -name "fastapi*" -o -name "boto3*" | grep -q .; then
    echo "⚠️  Warning: Some dependencies still found in source"
    find src -name "aiohttp*" -o -name "pybitget*" -o -name "fastapi*" -o -name "boto3*"
else
    echo "✅ No dependencies found in source - repository is clean!"
fi

echo ""
echo "📝 Next steps:"
echo "1. Run: ./deploy_clean.sh (installs deps in .aws-sam/ only)"
echo "2. Dependencies will be installed during SAM build"
echo "3. Source code remains clean for version control"