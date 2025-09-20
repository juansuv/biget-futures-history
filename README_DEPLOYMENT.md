# 🚀 Bitget Trading Orders - Clean Deployment Guide

## ✅ **Repository Structure (Clean)**

```
trading/
├── src/
│   ├── api/
│   │   ├── main.py              # FastAPI app with Mangum
│   │   └── requirements.txt     # FastAPI dependencies
│   ├── lambdas/
│   │   ├── coordinator/
│   │   │   ├── handler.py       # Coordinator Lambda
│   │   │   ├── config.py        # Bitget config
│   │   │   └── requirements.txt # python-bitget, boto3
│   │   ├── symbol_processor/
│   │   │   ├── handler.py       # Symbol processor
│   │   │   ├── config.py        # Bitget config
│   │   │   └── requirements.txt # python-bitget
│   │   └── result_collector/
│   │       ├── handler.py       # Result collector
│   │       └── requirements.txt # (empty)
│   └── config/                  # Shared config
├── template_complete.yaml       # CloudFormation template
├── deploy_clean.sh             # Clean deployment script
├── clean_repo.sh              # Repository cleaner
└── .gitignore                 # Ignores .aws-sam/ and deps
```

## 🧹 **Clean Development Workflow**

### **1. Keep Repository Clean**
```bash
# Clean any existing dependencies from source
./clean_repo.sh
```

### **2. Deploy with Clean Build**
```bash
# Deploy - installs dependencies only in .aws-sam/
./deploy_clean.sh
```

### **3. What Happens During Deploy:**
- ✅ **Source stays clean** - no dependencies added to `src/`
- ✅ **SAM installs deps** in `.aws-sam/build/` (ignored by git)
- ✅ **Each Lambda gets its deps** from `requirements.txt`
- ✅ **FastAPI gets Mangum** for Lambda compatibility
- ✅ **Coordinator gets pybitget** for Bitget API
- ✅ **All get boto3** for AWS services

## 🎯 **Benefits of Clean Deployment:**

| **Traditional** | **Clean Approach** |
|-----------------|-------------------|
| ❌ Dependencies in source | ✅ Dependencies only in `.aws-sam/` |
| ❌ Large git commits | ✅ Small, clean commits |
| ❌ Platform-specific binaries | ✅ Lambda-optimized builds |
| ❌ Mixed source/deps | ✅ Pure source code |

## 🚀 **Deployment Commands:**

### **Quick Deploy:**
```bash
./deploy_clean.sh
```

### **Manual Deploy:**
```bash
# Clean first
./clean_repo.sh

# Build (installs deps in .aws-sam/)
sam build --template-file template_complete.yaml

# Deploy
sam deploy --template-file template_complete.yaml \
  --stack-name bitget-clean-api \
  --capabilities CAPABILITY_IAM \
  --no-confirm-changeset
```

## 📦 **Dependency Management:**

### **FastAPI Lambda (`src/api/requirements.txt`):**
```
fastapi==0.104.1
mangum==0.17.0      # Lambda adapter
pydantic>=2.5.0
boto3
```

### **Coordinator Lambda (`src/lambdas/coordinator/requirements.txt`):**
```
python-bitget>=1.0.8
boto3
```

### **Symbol Processor Lambda (`src/lambdas/symbol_processor/requirements.txt`):**
```
python-bitget>=1.0.8
```

### **Result Collector Lambda (`src/lambdas/result_collector/requirements.txt`):**
```
# No external dependencies
```

## 🔍 **Verification:**

### **Check Repository is Clean:**
```bash
# Should show no dependencies in source
find src -name "pybitget*" -o -name "fastapi*" -o -name "boto3*"

# Should be empty output = clean!
```

### **Check Build Contains Dependencies:**
```bash
# After sam build, dependencies are here:
ls .aws-sam/build/FastApiFunction/
ls .aws-sam/build/CoordinatorFunction/
```

## 🎉 **Result After Deploy:**

- 🌐 **API Gateway URL** with FastAPI
- 📖 **Interactive docs** at `/docs`
- 🏠 **Landing page** at `/`
- ⚡ **4 Lambda functions** optimized
- 🔄 **Step Function** parallel processing
- 🧹 **Clean source code** for git

## 🧪 **Testing:**

### **Test API:**
```bash
# Get API URL from deploy output
API_URL="https://xyz.execute-api.us-east-1.amazonaws.com/Prod"

# Test endpoints
python test_complete_api.py $API_URL
```

### **Direct Lambda Test:**
```bash
aws lambda invoke \
  --function-name bitget-symbol-processor \
  --payload '{"symbol":"BTCUSDT"}' \
  response.json
```

## 📝 **Best Practices:**

1. ✅ **Always run `./clean_repo.sh` before commits**
2. ✅ **Use `./deploy_clean.sh` for deployments**
3. ✅ **Keep `requirements.txt` minimal per function**
4. ✅ **Test locally with virtual environments**
5. ✅ **Use `.gitignore` to ignore `.aws-sam/`**

## 🎯 **Next Steps:**

1. **Deploy:** `./deploy_clean.sh`
2. **Test:** Visit the API Gateway URL
3. **Develop:** Keep source clean with `./clean_repo.sh`
4. **Scale:** Add more symbols or customize logic

**Clean code, clean deploys, maximum performance!** 🚀