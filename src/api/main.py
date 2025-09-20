import json
import os
import boto3
import time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from mangum import Mangum

# Initialize FastAPI
app = FastAPI(
    title="Bitget Orders Extraction API",
    description="Ultra-fast API for Bitget trading orders extraction",
    version="3.0.0"
)

# Pydantic model
class OrderExtractionRequest(BaseModel):
    test_mode: bool = False

# AWS client and environment
stepfunctions = boto3.client("stepfunctions")
STEP_FUNCTION_ARN = os.environ.get("STEP_FUNCTION_ARN")




@app.post("/extract-orders")
async def extract_orders(request_data: OrderExtractionRequest):
    """
    Extract all orders using Step Function (complete flow)
    """
    try:
        if not STEP_FUNCTION_ARN:
            raise HTTPException(status_code=500, detail="Step Function ARN not configured")

        # Execute Step Function with minimal input
        execution_name = f"extract-{int(time.time())}"
        
        stepfunctions.start_execution(
            stateMachineArn=STEP_FUNCTION_ARN,
            name=execution_name,
            input=json.dumps({
                "collect_from_s3": True,
                "test_mode": request_data.test_mode
            })
        )

        return {
            "status": "started",
            "execution_name": execution_name
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Handler for AWS Lambda
handler = Mangum(app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)