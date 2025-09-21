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

# Pydantic models
class OrderExtractionRequest(BaseModel):
    test_mode: bool = False

class AnalyticsRequest(BaseModel):
    execution_name: str = None
    analysis_type: str = "full"  # 'full', 'summary', 'pnl', 'charts', 'regression'
    days_back: int = 30

# AWS clients and environment
stepfunctions = boto3.client("stepfunctions")
s3_client = boto3.client("s3")
lambda_client = boto3.client("lambda")
STEP_FUNCTION_ARN = os.environ.get("STEP_FUNCTION_ARN")
RESULTS_BUCKET = os.environ.get("RESULTS_BUCKET")
ANALYTICS_FUNCTION_NAME = os.environ.get("ANALYTICS_FUNCTION_NAME", "bitget-analytics-processor")

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


@app.post("/analytics")
async def run_analytics(request_data: AnalyticsRequest):
    """
    Ejecutar análisis estadístico completo de las órdenes
    """
    try:
        # Preparar payload para la Lambda de analytics
        analytics_payload = {
            "analysis_type": request_data.analysis_type,
            "execution_name": request_data.execution_name,
            "days_back": request_data.days_back
        }
        
        print(f"🚀 Starting analytics with payload: {analytics_payload}")
        
        # Invocar Lambda de analytics de forma asíncrona
        response = lambda_client.invoke(
            FunctionName=ANALYTICS_FUNCTION_NAME,
            InvocationType='RequestResponse',  # Síncrono para obtener resultado inmediato
            Payload=json.dumps(analytics_payload)
        )
        
        # Procesar respuesta
        response_payload = json.loads(response['Payload'].read())
        
        if response_payload.get('statusCode') == 200:
            analytics_result = json.loads(response_payload['body'])
            
            return {
                "status": "completed",
                "message": "Statistical analysis completed successfully",
                "analysis_type": request_data.analysis_type,
                "analytics_result": analytics_result
            }
        else:
            error_body = json.loads(response_payload.get('body', '{}'))
            raise HTTPException(
                status_code=response_payload.get('statusCode', 500),
                detail=error_body.get('error', 'Analytics processing failed')
            )
            
    except Exception as e:
        print(f"❌ Error in analytics endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/async/{execution_name}")
async def run_analytics_async(execution_name: str, analysis_type: str = "full", days_back: int = 30):
    """
    Ejecutar análisis estadístico de forma asíncrona (no bloquea)
    """
    try:
        # Preparar payload para la Lambda de analytics
        analytics_payload = {
            "analysis_type": analysis_type,
            "execution_name": execution_name,
            "days_back": days_back
        }
        
        print(f"🚀 Starting async analytics with payload: {analytics_payload}")
        
        # Invocar Lambda de analytics de forma asíncrona
        response = lambda_client.invoke(
            FunctionName=ANALYTICS_FUNCTION_NAME,
            InvocationType='Event',  # Asíncrono
            Payload=json.dumps(analytics_payload)
        )
        
        # Generar URL esperada del resultado
        timestamp = int(time.time())
        expected_s3_key = f"analytics/{timestamp}_{execution_name}_analysis.json"
        expected_url = f"https://{RESULTS_BUCKET}.s3.amazonaws.com/{expected_s3_key}"
        
        return {
            "status": "started",
            "message": "Statistical analysis started successfully",
            "execution_name": execution_name,
            "analysis_type": analysis_type,
            "estimated_completion_time": "1-3 minutes",
            "expected_result_url": expected_url
        }
            
    except Exception as e:
        print(f"❌ Error in async analytics endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Handler for AWS Lambda
handler = Mangum(app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)