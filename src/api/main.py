import json
import os
import boto3
import time
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.openapi.docs import get_swagger_ui_html
from pydantic import BaseModel
from mangum import Mangum

ROOT_PATH = os.environ.get("FASTAPI_ROOT_PATH", "")
STAGE_PREFIX = ROOT_PATH.rstrip('/') if ROOT_PATH else ''


def stage_path(path: str = '') -> str:
    suffix = path.lstrip('/')
    if STAGE_PREFIX:
        return f"{STAGE_PREFIX}/{suffix}" if suffix else (STAGE_PREFIX or '/')
    return f"/{suffix}" if suffix else '/'

# Initialize FastAPI
app = FastAPI(
    title="Bitget Trading Orders API",
    description="API completa para extraer órdenes de trading de Bitget usando AWS Lambda y Step Functions",
    version="2.0.0",
    root_path=ROOT_PATH,
    docs_url=None,
    redoc_url=None
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
stepfunctions = boto3.client('stepfunctions')
lambda_client = boto3.client('lambda')

# Environment variables (set by CloudFormation)
STEP_FUNCTION_ARN = os.environ.get('STEP_FUNCTION_ARN')

@app.get("/", response_class=HTMLResponse)
async def root():
    """Landing page with API documentation"""
    with open('src/api/index.html', 'r') as f:
        html_content = f.read()
    
    docs_href = stage_path('docs')
    health_href = stage_path('health')
    symbols_href = stage_path('get-symbols')
    extract_orders_href = stage_path('extract-orders')
    extract_single_href = stage_path('extract-single-symbol')
    base_path_hint = STAGE_PREFIX if STAGE_PREFIX else '/'
    
    html_content = html_content.replace('href="/health"', f'href="{health_href}"')
    html_content = html_content.replace('href="/get-symbols"', f'href="{symbols_href}"')
    html_content = html_content.replace('href="/docs"', f'href="{docs_href}"')
    html_content = html_content.replace('"/extract-orders"', f'"{extract_orders_href}"')
    html_content = html_content.replace('"/extract-single-symbol"', f'"{extract_single_href}"')
    html_content = html_content.replace('</body>', f'<p style="font-size: 0.9em; color: #555;">Base path para este despliegue: <code>{base_path_hint}</code></p></body>')
    
    return HTMLResponse(content=html_content)

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui():
    """Swagger UI con ruta compatible con API Gateway stages"""
    return get_swagger_ui_html(
        openapi_url=stage_path('openapi.json'),
        title="Bitget Trading Orders API - Docs"
    )

@app.get("/health")
async def health_check():
    """Health check del sistema"""
    return {
        "status": "healthy",
        "service": "bitget-orders-api",
        "version": "2.0.0",
        "timestamp": int(time.time() * 1000),
        "step_function_configured": STEP_FUNCTION_ARN is not None
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
            raise HTTPException(status_code=500, detail="Step Function ARN not configured")
        
        # Si no se proporcionan símbolos, obtenerlos del coordinador
        symbols = request.symbols
        if not symbols:
            try:
                coordinator_response = coordinator_lambda_handler.get_all_orders_secuencial(
                    FunctionName='bitget-coordinator',
                    Payload=json.dumps({"test_mode": request.test_mode})
                )
                
                coordinator_result = json.loads(coordinator_response['Payload'].read())
                if coordinator_result.get('statusCode') == 200:
                    body = json.loads(coordinator_result['body'])
                    symbols = body.get('symbols', [])[:10]  # Limitar a 10 para demo
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
            input=json.dumps({
                "symbols": symbols,
            })
        )
        
        return OrderExtractionResponse(
            status="success",
            message=f"Step Function execution started for {len(symbols)} symbols",
            data={
                "symbols": symbols,
                "execution_name": execution_name,
                "symbols_count": len(symbols)
            },
            execution_arn=response['executionArn']
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
            FunctionName='bitget-symbol-processor',
            Payload=json.dumps({"symbol": request.symbol})
        )
        
        result = json.loads(response['Payload'].read())
        
        if result.get('statusCode') == 200:
            return OrderExtractionResponse(
                status="success",
                message=f"Orders extracted for {request.symbol}",
                data=result
            )
        else:
            raise HTTPException(status_code=500, detail=result.get('error', 'Unknown error'))
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get-symbols")
async def get_symbols():
    """
    Obtener lista de símbolos disponibles desde Bitget
    """
    try:
        response = lambda_client.invoke(
            FunctionName='bitget-coordinator',
            Payload=json.dumps({"test_mode": True})
        )
        
        result = json.loads(response['Payload'].read())
        
        if result.get('statusCode') == 200:
            body = json.loads(result['body'])
            return {
                "status": "success",
                "symbols": body.get('symbols', []),
                "count": len(body.get('symbols', []))
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
            "status": response['status'],
            "start_date": response['startDate'].isoformat(),
            "definition": response.get('definition')
        }
        
        if response['status'] == 'SUCCEEDED' and 'output' in response:
            try:
                output = json.loads(response['output'])
                if 'final_result' in output and 'Payload' in output['final_result']:
                    final_data = json.loads(output['final_result']['Payload']['body'])
                    result['summary'] = {
                        "total_orders": final_data.get('total_orders', 0),
                        "symbols_processed": final_data.get('symbols_processed', 0),
                        "symbols_failed": final_data.get('symbols_failed', 0)
                    }
            except:
                pass
        
        if response['status'] == 'FAILED':
            result['error'] = response.get('error', 'Unknown error')
            
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/list-executions")
async def list_recent_executions():
    """
    Listar ejecuciones recientes del Step Function
    """
    try:
        if not STEP_FUNCTION_ARN:
            raise HTTPException(status_code=500, detail="Step Function ARN not configured")
            
        response = stepfunctions.list_executions(
            stateMachineArn=STEP_FUNCTION_ARN,
            maxResults=10
        )
        
        executions = []
        for execution in response['executions']:
            executions.append({
                "execution_arn": execution['executionArn'],
                "name": execution['name'],
                "status": execution['status'],
                "start_date": execution['startDate'].isoformat(),
                "stop_date": execution.get('stopDate', '').isoformat() if execution.get('stopDate') else None
            })
        
        return {
            "status": "success",
            "executions": executions,
            "count": len(executions)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Handler para AWS Lambda
handler = Mangum(app)
