import json
import os
import boto3
import time
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException
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
    return {
        "status": "healthy",
        "service": "bitget-orders-api",
        "version": "2.0.0",
        "timestamp": int(time.time() * 1000),
        "step_function_configured": STEP_FUNCTION_ARN is not None,
    }


@app.post("/extract-orders", response_model=OrderExtractionResponse)
async def extract_orders(request: OrderExtractionRequest):
    """
    Extraer órdenes usando Step Function (flujo completo)

    Este endpoint:
    1. Obtiene símbolos automáticamente si no se proporcionan
    2. Ejecuta el Step Function con procesamiento paralelo
    3. Devuelve el ARN de ejecución para seguimiento
    """
    try:
        if not STEP_FUNCTION_ARN:
            raise HTTPException(
                status_code=500, detail="Step Function ARN not configured"
            )

        # Si no se proporcionan símbolos, obtenerlos del coordinador
        symbols = request.symbols
        if not symbols:
            try:
                coordinator_response = lambda_client.invoke(
                    FunctionName="bitget-coordinator",
                    Payload=json.dumps({"test_mode": request.test_mode}),
                )

                coordinator_result = json.loads(coordinator_response["Payload"].read())
                if coordinator_result.get("statusCode") == 200:
                    body = json.loads(coordinator_result["body"])
                    symbols = body.get("symbols", [])  # Limitar a 10 para demo
                else:
                    raise Exception("Coordinator failed")

            except Exception as e:
                # Usar símbolos por defecto si falla el coordinador
                symbols = ["BTCUSDT", "ETHUSDT", "ADAUSDT"]

        # Ejecutar Step Function
        execution_name = f"bitget-extraction-{int(time.time())}"

        response = stepfunctions.start_execution(
            stateMachineArn=STEP_FUNCTION_ARN,
            name=execution_name,
            input=json.dumps(
                {
                    "symbols": symbols,
                }
            ),
        )

        # Crear link de descarga
        execution_arn_encoded = response["executionArn"].replace(":", "_")
        download_link = stage_path(f"download-result/{execution_arn_encoded}")
        status_link = stage_path(f"execution-status/{execution_arn_encoded}")

        return OrderExtractionResponse(
            status="success",
            message=f"Step Function execution started for {len(symbols)} symbols. Wait for completion, then use download_link.",
            data={
                "symbols": symbols,
                "execution_name": execution_name,
                "symbols_count": len(symbols),
                "download_link": download_link,
                "status_link": status_link,
                "instructions": "1. Check status_link until status='SUCCEEDED', 2. Then use download_link to get JSON file",
                "execution_arn_encoded": execution_arn_encoded
            },
            execution_arn=response["executionArn"],
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/extract-single-symbol", response_model=OrderExtractionResponse)
async def extract_single_symbol(request: SymbolExtractionRequest):
    """
    Extraer órdenes de un símbolo específico (directo)

    Ejecuta directamente la Lambda procesadora de símbolos
    """
    try:
        response = lambda_client.invoke(
            FunctionName="bitget-symbol-processor",
            Payload=json.dumps({"symbol": request.symbol}),
        )

        result = json.loads(response["Payload"].read())

        if result.get("statusCode") == 200:
            return OrderExtractionResponse(
                status="success",
                message=f"Orders extracted for {request.symbol}",
                data=result,
            )
        else:
            raise HTTPException(
                status_code=500, detail=result.get("error", "Unknown error")
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/get-symbols")
async def get_symbols():
    """
    Obtener lista de símbolos disponibles desde Bitget
    """
    try:
        response = lambda_client.invoke(
            FunctionName="bitget-coordinator", Payload=json.dumps({"test_mode": True})
        )

        result = json.loads(response["Payload"].read())

        if result.get("statusCode") == 200:
            body = json.loads(result["body"])
            return {
                "status": "success",
                "symbols": body.get("symbols", []),
                "count": len(body.get("symbols", [])),
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to get symbols")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
                            "orders_truncated": final_data.get("orders_truncated", False)
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

        # Parsear el output para obtener el resultado final
        output = json.loads(response["output"])

        # Extraer el resultado del collect_result
        final_result = None
        s3_key = None
        
        if "final_result" in output and "Payload" in output["final_result"]:
            payload = output["final_result"]["Payload"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            if "body" in payload:
                body = json.loads(payload["body"])
                # Check if result was stored in S3
                if body.get("orders_truncated") and body.get("s3_key"):
                    s3_key = body["s3_key"]
                    bucket_name = body.get("s3_bucket", os.environ.get("RESULTS_BUCKET"))
                    
                    # Download from S3
                    s3_client = boto3.client("s3")
                    s3_response = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
                    final_result = json.loads(s3_response["Body"].read().decode("utf-8"))
                else:
                    final_result = body
            else:
                final_result = payload
        else:
            final_result = output

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


# Handler para AWS Lambda
handler = Mangum(app)
