from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import boto3
import json
from typing import Dict, Any, Optional
from pydantic import BaseModel
from src.lambdas.coordinator.handler import lambda_handler as coordinator_handler
from src.lambdas.symbol_processor.handler import lambda_handler as symbol_processor_handler
from src.lambdas.result_collector.handler import lambda_handler as result_collector_handler

app = FastAPI(
    title="Bitget Trading Orders API",
    description="API para extraer órdenes de trading de Bitget usando AWS Lambda y Step Functions",
    version="1.0.0"
)

class OrderExtractionRequest(BaseModel):
    step_function_arn: Optional[str] = None
    test_mode: bool = False

class OrderExtractionResponse(BaseModel):
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None
    
class SymbolExtractionRequest(BaseModel):
    symbol: str
    test_mode: bool = False

@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint"""
    return {
        "message": "Bitget Trading Orders API",
        "version": "1.0.0",
        "endpoints": {
            "extract_orders": "/extract-orders",
            "health": "/health",
            "test_coordinator": "/test/coordinator",
            "test_symbol_processor": "/test/symbol-processor",
            "test_result_collector": "/test/result-collector"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "bitget-orders-api"}

@app.post("/extract-orders", response_model=OrderExtractionResponse)
async def extract_orders(request: OrderExtractionRequest):
    """
    Endpoint principal para extraer órdenes de Bitget
    Ejecuta el coordinador Lambda que inicia el Step Function
    """
    try:
        event = {
            "step_function_arn": request.step_function_arn,
            "test_mode": request.test_mode
        }
        print(f"Received request: {event}")
        # Execute coordinator Lambda
        result = coordinator_handler(event, None)
        
        if result['statusCode'] == 200:
            body = json.loads(result['body'])
            return OrderExtractionResponse(
                status="success",
                message=body['message'],
                data=body
            )
        else:
            body = json.loads(result['body'])
            raise HTTPException(
                status_code=result['statusCode'],
                detail=body.get('error', 'Unknown error')
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/extract-symbols", response_model=OrderExtractionResponse)
async def extract_symbols(request: SymbolExtractionRequest):
    """
    Endpoint principal para extraer órdenes de Bitget
    Ejecuta el coordinador Lambda que inicia el Step Function
    """
    try:
        event = {
            "symbol": request.symbol,
            "test_mode": request.test_mode
        }
        # Execute coordinator Lambda
        result = symbol_processor_handler(event, None)
        
        if result['statusCode'] == 200:
            #print(f"Symbol processor result: {result}")
            print("total orders", len(result['orders']))
            body = result
            
            
            return OrderExtractionResponse(
                status="success",
                message="Symbol processed successfully",
                data=body
            )
        else:
            body = json.loads(result['body'])
            raise HTTPException(
                status_code=result['statusCode'],
                detail=body.get('error', 'Unknown error')
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/test/coordinator")
async def test_coordinator():
    """
    Endpoint de prueba para el Lambda coordinador
    """
    try:
        event = {"test_mode": True}
        result = coordinator_handler(event, None)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/test/symbol-processor")
async def test_symbol_processor(symbol: str = "BTCUSDT"):
    """
    Endpoint de prueba para el Lambda procesador de símbolos
    """
    try:
        event = {"symbol": symbol}
        result = symbol_processor_handler(event, None)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/test/result-collector")
async def test_result_collector():
    """
    Endpoint de prueba para el Lambda recolector de resultados
    """
    try:
        # Mock parallel results for testing
        mock_results = [
            {
                "Payload": {
                    "statusCode": 200,
                    "symbol": "BTCUSDT",
                    "orders_count": 5,
                    "orders": [
                        {
                            "orderId": "test123",
                            "symbol": "BTCUSDT",
                            "size": "0.1",
                            "price": "50000",
                            "side": "buy",
                            "createTime": "1640995200000"
                        }
                    ],
                    "processed_at": 1640995200000
                }
            }
        ]
        
        event = {"parallel_results": mock_results}
        result = result_collector_handler(event, None)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 