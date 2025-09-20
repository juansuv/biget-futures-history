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
s3_client = boto3.client("s3")
STEP_FUNCTION_ARN = os.environ.get("STEP_FUNCTION_ARN")
RESULTS_BUCKET = os.environ.get("RESULTS_BUCKET")




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

        # Generate expected result URL for the user
        timestamp = int(time.time())
        expected_s3_key = f"results/{timestamp}_{execution_name}.json"
        expected_public_url = f"https://{RESULTS_BUCKET}.s3.amazonaws.com/{expected_s3_key}"
        
        return {
            "status": "started",
            "execution_name": execution_name,
            "message": "Step Function started successfully. Results will be available at the URL below when processing completes.",
            "estimated_completion_time": "5-10 minutes",
            "result_url": expected_public_url,
            "check_status_url": f"https://console.aws.amazon.com/states/home?region=us-east-1#/executions/details/{STEP_FUNCTION_ARN.replace(':stateMachine:', ':execution:')}:{execution_name}"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/execution-status/{execution_name}")
async def get_execution_status(execution_name: str):
    """
    Check execution status and get result URL when completed
    """
    try:
        if not STEP_FUNCTION_ARN:
            raise HTTPException(status_code=500, detail="Step Function ARN not configured")
        
        # Build execution ARN
        execution_arn = STEP_FUNCTION_ARN.replace(':stateMachine:', ':execution:') + f":{execution_name}"
        
        # Check execution status
        response = stepfunctions.describe_execution(executionArn=execution_arn)
        status = response.get('status', 'UNKNOWN')
        
        result = {
            "execution_name": execution_name,
            "status": status.lower(),
            "start_date": response.get('startDate').isoformat() if response.get('startDate') else None
        }
        
        if status == 'SUCCEEDED':
            # Look for the result file in S3
            try:
                # List files in results folder for this execution
                response = s3_client.list_objects_v2(
                    Bucket=RESULTS_BUCKET,
                    Prefix=f"results/",
                    MaxKeys=1000
                )
                
                # Find the file that matches this execution
                result_file = None
                if 'Contents' in response:
                    for obj in response['Contents']:
                        if execution_name in obj['Key'] and obj['Key'].endswith('.json'):
                            result_file = obj['Key']
                            break
                
                if result_file:
                    public_url = f"https://{RESULTS_BUCKET}.s3.amazonaws.com/{result_file}"
                    result.update({
                        "result_available": True,
                        "result_url": public_url,
                        "s3_key": result_file
                    })
                else:
                    result["result_available"] = False
                    result["message"] = "Execution completed but result file not found"
                    
            except Exception as e:
                result["result_available"] = False
                result["error"] = f"Error checking S3: {str(e)}"
                
        elif status == 'FAILED':
            result["error"] = response.get('error', 'Unknown error')
            result["cause"] = response.get('cause', 'Unknown cause')
        elif status == 'RUNNING':
            result["message"] = "Execution in progress..."
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Handler for AWS Lambda
handler = Mangum(app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)