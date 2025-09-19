# Bitget Trading Orders Extraction

Solución en Python (FastAPI) que se conecta a Bitget y extrae las órdenes del usuario usando AWS Lambda y AWS Step Functions.

## Arquitectura

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│   FastAPI       │    │   Coordinator    │    │   Step Function     │
│   Application   │───▶│   Lambda         │───▶│   (Parallel Map)    │
└─────────────────┘    └──────────────────┘    └─────────────────────┘
                                                           │
                       ┌─────────────────────────────────────┘
                       ▼
┌─────────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│   Result Collector  │◀───│   Symbol         │    │   Symbol            │
│   Lambda            │    │   Processor      │    │   Processor         │
└─────────────────────┘    │   Lambda 1       │    │   Lambda N          │
                           └──────────────────┘    └─────────────────────┘
```

## Componentes

### 1. Lambda Coordinadora (`src/lambdas/coordinator/`)
- Detecta todos los símbolos con trades del usuario
- Inicia el Step Function pasando la lista de símbolos

### 2. Step Function (`src/step_functions/`)
- Usa un estado tipo Map en paralelo
- Procesa cada símbolo de forma independiente

### 3. Lambda Procesadora de Símbolos (`src/lambdas/symbol_processor/`)
- Se conecta a Bitget
- Extrae todas las órdenes del símbolo específico
- Devuelve el resultado en JSON

### 4. Lambda Recolectora (`src/lambdas/result_collector/`)
- Combina todos los resultados en un único JSON
- Ordena las órdenes cronológicamente

## Configuración

### Credenciales de Bitget
```
API Key: bg_680026a00a63d58058c738c952ce67a2
Secret Key: 7abac4a9404e82830db5f9db5e867a8370c7e59dc74e52615c59552d0afbd7c9
Passphrase: 22Dominic22
```

### Variables de Entorno
```bash
BITGET_API_KEY=bg_680026a00a63d58058c738c952ce67a2
BITGET_SECRET_KEY=7abac4a9404e82830db5f9db5e867a8370c7e59dc74e52615c59552d0afbd7c9
BITGET_PASSPHRASE=22Dominic22
```

## Instalación

1. **Instalar dependencias:**
```bash
pip install -r requirements.txt
```

2. **Configurar AWS CLI:**
```bash
aws configure
```

3. **Instalar SAM CLI:**
```bash
pip install aws-sam-cli
```

## Despliegue

### Opción 1: Script Automático
```bash
./deploy.sh
```

### Opción 2: Manual
```bash
# Build
sam build

# Deploy
sam deploy --guided --stack-name bitget-trading-orders
```

### Opción 3: Obtener ARN de Step Function
```bash
# Después del despliegue, obtener el ARN:
aws stepfunctions list-state-machines --query 'stateMachines[?name==`bitget-order-extraction`].stateMachineArn' --output text

# O ver todos los outputs del stack:
aws cloudformation describe-stacks --stack-name bitget-trading-orders --query 'Stacks[0].Outputs'
```

## Uso

### 1. Ejecutar FastAPI localmente
```bash
python main.py
```

### 2. Endpoints disponibles

- **POST /extract-orders** - Extrae todas las órdenes
- **GET /health** - Health check
- **POST /test/coordinator** - Prueba el coordinador
- **POST /test/symbol-processor** - Prueba el procesador
- **POST /test/result-collector** - Prueba el recolector

### 3. Ejemplo de uso
```bash
curl -X POST "http://localhost:8000/extract-orders" \
     -H "Content-Type: application/json" \
     -d '{"test_mode": false}'
```

## Características

- ✅ **Solo órdenes Futures**: Extrae únicamente órdenes de tipo Futures
- ✅ **Historial completo**: Obtiene el historial completo disponible
- ✅ **Ejecución paralela**: Step Function ejecuta en paralelo para múltiples símbolos
- ✅ **Ordenamiento cronológico**: Resultados ordenados por fecha
- ✅ **Manejo de errores**: Gestión robusta de errores y reintentos
- ✅ **Paginación**: Maneja la paginación de la API de Bitget

## Estructura del Proyecto

```
trading/
├── src/
│   ├── config/              # Configuración
│   ├── lambdas/
│   │   ├── coordinator/     # Lambda coordinadora
│   │   ├── symbol_processor/# Lambda procesadora
│   │   └── result_collector/# Lambda recolectora
│   └── step_functions/      # Definición Step Function
├── tests/                   # Tests
├── main.py                  # FastAPI application
├── template.yaml            # SAM template
├── deploy.sh               # Script de despliegue
└── requirements.txt        # Dependencias
```

## Testing

### Pruebas locales
```bash
# Probar coordinador
curl -X POST "http://localhost:8000/test/coordinator"

# Probar procesador de símbolos
curl -X POST "http://localhost:8000/test/symbol-processor?symbol=BTCUSDT"

# Probar recolector
curl -X POST "http://localhost:8000/test/result-collector"
```

## Consideraciones de Seguridad

- Las credenciales se manejan como parámetros de CloudFormation
- Se usan variables de entorno para la configuración
- IAM roles con permisos mínimos necesarios

## Limitaciones de Rate Limit

- Bitget API: 10 requests/second/UID
- Se implementan delays entre requests para respetar límites
- Manejo de paginación para grandes volúmenes de datos