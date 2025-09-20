import json
import os
import boto3
import time
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel
from mangum import Mangum

ROOT_PATH = os.environ.get("FASTAPI_ROOT_PATH", "")
STAGE_PREFIX = ROOT_PATH.rstrip("/") if ROOT_PATH else ""


def stage_path(path: str = "") -> str:
    suffix = path.lstrip("/")
    if STAGE_PREFIX:
        return f"{STAGE_PREFIX}/{suffix}" if suffix else (STAGE_PREFIX or "/")
    return f"/{suffix}" if suffix else "/"

def get_base_url(request: Request) -> str:
    """Get the base URL for the current request"""
    # Try to get from API Gateway headers first
    host = request.headers.get("host")
    if not host:
        host = request.url.hostname
        if request.url.port:
            host = f"{host}:{request.url.port}"
    
    # Use https for API Gateway
    scheme = "https" if "amazonaws.com" in str(host) else request.url.scheme
    
    base_url = f"{scheme}://{host}"
    if STAGE_PREFIX:
        base_url += STAGE_PREFIX
    
    return base_url

def full_url(request: Request, path: str = "") -> str:
    """Generate a full URL for the given path"""
    base = get_base_url(request)
    suffix = path.lstrip("/")
    return f"{base}/{suffix}" if suffix else base


# Initialize FastAPI
app = FastAPI(
    title="Bitget Trading Orders API",
    description="API completa para extraer órdenes de trading de Bitget usando AWS Lambda y Step Functions",
    version="2.0.0",
    root_path=ROOT_PATH,
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)


# Pydantic models
class OrderExtractionRequest(BaseModel):
    symbols: Optional[List[str]] = None
    test_mode: bool = False


class SymbolExtractionRequest(BaseModel):
    symbol: str


class StepFunctionExecutionRequest(BaseModel):
    symbols: List[str]
    execution_name: Optional[str] = None


class OrderExtractionResponse(BaseModel):
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None
    execution_arn: Optional[str] = None


# AWS clients
stepfunctions = boto3.client("stepfunctions")
lambda_client = boto3.client("lambda")

# Environment variables (set by CloudFormation)
STEP_FUNCTION_ARN = os.environ.get("STEP_FUNCTION_ARN")


@app.get("/", response_class=HTMLResponse)
async def root():
    """Landing page with API documentation"""
    import os

    current_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(current_dir, "index.html")

    try:
        with open(html_path, "r") as f:
            html_content = f.read()
    except FileNotFoundError:
        # Fallback HTML if file not found
        html_content = """
        <!DOCTYPE html>
        <html>
        <head><title>Bitget Trading Orders API</title></head>
        <body>
            <h1>🚀 Bitget Trading Orders API</h1>
            <p>API endpoint is running. <a href="/docs">View documentation</a></p>
        </body>
        </html>
        """

    docs_href = stage_path("docs")
    health_href = stage_path("health")
    symbols_href = stage_path("get-symbols")
    extract_orders_href = stage_path("extract-orders")
    extract_single_href = stage_path("extract-single-symbol")
    base_path_hint = STAGE_PREFIX if STAGE_PREFIX else "/"

    html_content = html_content.replace('href="/health"', f'href="{health_href}"')
    html_content = html_content.replace('href="/get-symbols"', f'href="{symbols_href}"')
    html_content = html_content.replace('href="/docs"', f'href="{docs_href}"')
    html_content = html_content.replace('"/extract-orders"', f'"{extract_orders_href}"')
    html_content = html_content.replace(
        '"/extract-single-symbol"', f'"{extract_single_href}"'
    )
    html_content = html_content.replace(
        "</body>",
        f'<p style="font-size: 0.9em; color: #555;">Base path para este despliegue: <code>{base_path_hint}</code></p></body>',
    )

    return HTMLResponse(content=html_content)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    # Remove the problematic servers configuration
    openapi_schema.pop("servers", None)
    app.openapi_schema = openapi_schema
    return app.openapi_schema


@app.get("/openapi.json", include_in_schema=False)
async def get_openapi_endpoint():
    return JSONResponse(custom_openapi())


@app.get("/docs", include_in_schema=False)
async def get_swagger_ui():
    return get_swagger_ui_html(
        openapi_url=stage_path("openapi.json"),
        title=app.title + " - Swagger UI",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui.css",
    )


@app.get("/docs-static", response_class=HTMLResponse, include_in_schema=False)
async def docs_static():
    """Static API documentation"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    docs_path = os.path.join(current_dir, "templates", "docs.html")

    try:
        with open(docs_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        return HTMLResponse(
            content="""
        <html>
        <body>
            <h1>📖 API Documentation</h1>
            <p>Documentation file not found. <a href="/">Return to main page</a></p>
        </body>
        </html>
        """,
            status_code=404,
        )


@app.get("/health")
async def health_check():
    """Health check del sistema"""
    return {"status": "healthy"}


@app.post("/extract-orders")
async def extract_orders(request_data: OrderExtractionRequest):
    """
    Extraer órdenes usando Step Function (flujo completo)
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
                "test_mode": request_data.test_mode,
                "mode": "test" if request_data.test_mode else "production"
            })
        )

        return {
            "status": "started",
            "execution_name": execution_name
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/extract-single-symbol")
async def extract_single_symbol(request: SymbolExtractionRequest):
    """
    Extraer órdenes de un símbolo específico (directo)
    """
    try:
        lambda_client.invoke(
            FunctionName="bitget-symbol-processor",
            Payload=json.dumps({"symbol": request.symbol}),
            InvocationType='Event'  # Async invoke
        )

        return {"status": "started", "symbol": request.symbol}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/get-symbols")
async def get_symbols():
    """
    Obtener lista de símbolos disponibles (predefinidos para testing)
    """
    return {
        "symbols": ["BTCUSDT", "ETHUSDT", "ADAUSDT", "DOGEUSDT", "SOLUSDT"],
        "count": 5
    }


@app.get("/execution-status/{execution_arn_path:path}")
async def get_execution_status(execution_arn_path: str):
    """
    Verificar estado de una ejecución de Step Function
    """
    try:
        # Reconstruir ARN (viene como path parameter)
        execution_arn = execution_arn_path.replace("_", ":")

        response = stepfunctions.describe_execution(executionArn=execution_arn)

        result = {
            "execution_arn": execution_arn,
            "status": response["status"],
            "start_date": response["startDate"].isoformat(),
            "definition": response.get("definition"),
        }

        if response["status"] == "SUCCEEDED" and "output" in response:
            try:
                output = json.loads(response["output"])
                if "final_result" in output and "Payload" in output["final_result"]:
                    payload = output["final_result"]["Payload"]
                    if isinstance(payload, str):
                        payload = json.loads(payload)
                    if "body" in payload:
                        final_data = json.loads(payload["body"])
                        result["summary"] = {
                            "total_orders": final_data.get("total_orders", 0),
                            "symbols_processed": final_data.get("symbols_processed", 0),
                            "symbols_failed": final_data.get("symbols_failed", 0),
                            "s3_key": final_data.get("s3_key"),
                            "orders_truncated": final_data.get("orders_truncated", False),
                            "direct_download_url": final_data.get("direct_download_url")
                        }
            except Exception as e:
                print(f"Error parsing execution output: {e}")
                pass

        if response["status"] == "FAILED":
            result["error"] = response.get("error", "Unknown error")

        return result

    except Exception as e:
        error_msg = str(e)
        if "does not exist" in error_msg:
            raise HTTPException(status_code=404, detail="Execution not found")
        elif "AccessDenied" in error_msg or "Forbidden" in error_msg:
            raise HTTPException(status_code=403, detail=f"Access denied to Step Functions: {error_msg}")
        else:
            raise HTTPException(status_code=500, detail=f"Error: {error_msg}")


@app.get("/list-executions")
async def list_recent_executions():
    """
    Listar ejecuciones recientes del Step Function
    """
    try:
        if not STEP_FUNCTION_ARN:
            raise HTTPException(
                status_code=500, detail="Step Function ARN not configured"
            )

        response = stepfunctions.list_executions(
            stateMachineArn=STEP_FUNCTION_ARN, maxResults=10
        )

        executions = []
        for execution in response["executions"]:
            executions.append(
                {
                    "execution_arn": execution["executionArn"],
                    "name": execution["name"],
                    "status": execution["status"],
                    "start_date": execution["startDate"].isoformat(),
                    "stop_date": (
                        execution.get("stopDate", "").isoformat()
                        if execution.get("stopDate")
                        else None
                    ),
                }
            )

        return {"status": "success", "executions": executions, "count": len(executions)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/download-result/{execution_arn_encoded}")
async def download_result(execution_arn_encoded: str):
    """
    Descargar resultado JSON del Step Function
    """
    return await _download_result_internal(execution_arn_encoded, debug=False)

@app.get("/download-result-debug/{execution_arn_encoded}")
async def download_result_debug(execution_arn_encoded: str):
    """
    Descargar resultado JSON del Step Function con información de debug
    """
    return await _download_result_internal(execution_arn_encoded, debug=True)

async def _download_result_internal(execution_arn_encoded: str, debug: bool = False):
    """
    Descargar resultado JSON del Step Function
    """
    try:
        # Decodificar ARN
        execution_arn = execution_arn_encoded.replace("_", ":")

        # Obtener el estado de la ejecución
        response = stepfunctions.describe_execution(executionArn=execution_arn)

        if response["status"] != "SUCCEEDED":
            raise HTTPException(
                status_code=400,
                detail=f"Execution not completed yet. Status: {response['status']}",
            )

        if "output" not in response:
            raise HTTPException(status_code=404, detail="No output available")

        # Parse el output para obtener el resultado final
        output = json.loads(response["output"])

        # Debug info
        debug_info = {
            "bucket_env": os.environ.get("RESULTS_BUCKET"),
            "execution_arn": execution_arn,
            "execution_status": response["status"]
        } if debug else None

        # Extraer el resultado del collect_result
        final_result = None
        s3_key = None
        
        if "final_result" in output and "Payload" in output["final_result"]:
            payload = output["final_result"]["Payload"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            if "body" in payload:
                body = json.loads(payload["body"])
                
                if debug:
                    debug_info.update({
                        "body_keys": list(body.keys()),
                        "orders_truncated": body.get("orders_truncated"),
                        "s3_key": body.get("s3_key"),
                        "s3_bucket": body.get("s3_bucket"),
                        "direct_download_url": body.get("direct_download_url")
                    })
                
                # Check if result was stored in S3
                if body.get("s3_key") and not body.get("s3_fallback_failed"):
                    s3_key = body["s3_key"]
                    bucket_name = body.get("s3_bucket", os.environ.get("RESULTS_BUCKET"))
                    
                    if bucket_name and s3_key:
                        print(f"Attempting to download from S3: s3://{bucket_name}/{s3_key}")
                        
                        # Download from S3
                        s3_client = boto3.client("s3")
                        try:
                            s3_response = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
                            final_result = json.loads(s3_response["Body"].read().decode("utf-8"))
                            print(f"Successfully downloaded result from S3: {len(final_result.get('orders', []))} orders")
                        except Exception as s3_error:
                            print(f"S3 error: {s3_error}")
                            print(f"Bucket: {bucket_name}, Key: {s3_key}")
                            print(f"Environment RESULTS_BUCKET: {os.environ.get('RESULTS_BUCKET')}")
                            
                            if debug:
                                return {
                                    "error": "S3 access failed",
                                    "s3_error": str(s3_error),
                                    "debug_info": debug_info,
                                    "bucket_name": bucket_name,
                                    "s3_key": s3_key
                                }
                            
                            raise HTTPException(status_code=500, detail=f"S3 access error: {s3_error}")
                    else:
                        print("Missing bucket_name or s3_key, using body directly")
                        final_result = body
                else:
                    # Either no S3 key or S3 fallback failed, use body directly
                    print("No S3 key or S3 fallback failed, using body directly")
                    final_result = body
            else:
                final_result = payload
        else:
            final_result = output
            
        # Add debug info if requested
        if debug and debug_info:
            if isinstance(final_result, dict):
                final_result["debug_info"] = debug_info
            else:
                final_result = {"result": final_result, "debug_info": debug_info}

        # Crear nombre de archivo con timestamp
        timestamp = int(time.time())
        filename = f"bitget_orders_{timestamp}.json"

        # Retornar como descarga
        return Response(
            content=json.dumps(final_result, indent=2, ensure_ascii=False),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": "application/json; charset=utf-8",
            },
        )

    except Exception as e:
        error_msg = str(e)
        if "does not exist" in error_msg:
            raise HTTPException(status_code=404, detail="Execution not found")
        elif "AccessDenied" in error_msg or "Forbidden" in error_msg:
            raise HTTPException(status_code=403, detail=f"Access denied: {error_msg}")
        elif "NoSuchBucket" in error_msg:
            raise HTTPException(status_code=404, detail="S3 bucket not found")
        elif "NoSuchKey" in error_msg:
            raise HTTPException(status_code=404, detail="Result file not found in S3")
        else:
            raise HTTPException(status_code=500, detail=f"Error: {error_msg}")


@app.get("/s3-download-url/{bucket_name}/{s3_key:path}")
async def generate_s3_download_url(bucket_name: str, s3_key: str, expires_in: int = 3600):
    """
    Generate a presigned URL for direct S3 download
    """
    try:
        s3_client = boto3.client("s3")
        
        # Generate presigned URL
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': s3_key},
            ExpiresIn=expires_in
        )
        
        return {
            "presigned_url": presigned_url,
            "expires_in_seconds": expires_in,
            "bucket": bucket_name,
            "key": s3_key
        }
        
    except Exception as e:
        error_msg = str(e)
        if "NoSuchBucket" in error_msg:
            raise HTTPException(status_code=404, detail="S3 bucket not found")
        elif "NoSuchKey" in error_msg:
            raise HTTPException(status_code=404, detail="S3 object not found")
        elif "AccessDenied" in error_msg:
            raise HTTPException(status_code=403, detail="Access denied to S3")
        else:
            raise HTTPException(status_code=500, detail=f"Error generating presigned URL: {error_msg}")


# Handler para AWS Lambda
handler = Mangum(app)

if __name__ == "__main__":
    # Usa FASTAPI_HOST/FASTAPI_PORT si quieres sobreescribir
    host = os.getenv("FASTAPI_HOST", "127.0.0.1")
    port = int(os.getenv("FASTAPI_PORT", "8000"))

    import uvicorn
    uvicorn.run(
        "src.api.main:app",  # apunta al objeto app
        host=host,
        port=port,
        reload=True
    )