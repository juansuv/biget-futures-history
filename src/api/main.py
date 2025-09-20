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
            "estimated_completion_time": "1-2 minutes",
            "result_url": expected_public_url
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/execution-status/{execution_name}")
async def get_execution_status(execution_name: str):
    """
    Check execution status - simple version
    """
    try:
        if not STEP_FUNCTION_ARN:
            raise HTTPException(status_code=500, detail="Step Function ARN not configured")
        
        # Build execution ARN
        execution_arn = STEP_FUNCTION_ARN.replace(':stateMachine:', ':execution:') + f":{execution_name}"
        
        # Check execution status with error handling
        try:
            response = stepfunctions.describe_execution(executionArn=execution_arn)
        except:
            return {
                "execution_name": execution_name,
                "status": "not_found",
                "message": "Execution not found or still starting"
            }
        
        status = response.get('status', 'UNKNOWN')
        
        result = {
            "execution_name": execution_name,
            "status": status.lower()
        }
        
        # Add dates if available
        if response.get('startDate'):
            result["start_date"] = response.get('startDate').isoformat()
        
        if response.get('stopDate'):
            result["stop_date"] = response.get('stopDate').isoformat()
            # Add duration
            if response.get('startDate'):
                duration = (response.get('stopDate') - response.get('startDate')).total_seconds()
                result["duration_seconds"] = f"{int(duration)} seconds"
        
        # Add status-specific info
        if status == 'SUCCEEDED':
            # Look for the result file in S3
            try:
                response_s3 = s3_client.list_objects_v2(
                    Bucket=RESULTS_BUCKET,
                    Prefix=f"results/",
                    MaxKeys=1000
                )
                
                # Find the file that matches this execution
                result_file = None
                if 'Contents' in response_s3:
                    for obj in response_s3['Contents']:
                        if execution_name in obj['Key'] and obj['Key'].endswith('.json'):
                            result_file = obj['Key']
                            break
                
                if result_file:
                    public_url = f"https://{RESULTS_BUCKET}.s3.amazonaws.com/{result_file}"
                    result.update({
                        "result_available": True,
                        "result_url": public_url,
                        #"s3_key": result_file,
                        "message": "Execution completed successfully"
                    })
                else:
                    result.update({
                        "result_available": False,
                        "message": "Execution completed but result file not found"
                    })
                    
            except Exception as e:
                result.update({
                    "result_available": False,
                    "message": f"Execution completed but error checking S3: {str(e)}"
                })
        elif status == 'RUNNING':
            result["result_available"] = False
            result["message"] = "Execution in progress..."
        elif status == 'FAILED':
            result["result_available"] = False
            result["message"] = "Execution failed"
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Handler for AWS Lambda
handler = Mangum(app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)