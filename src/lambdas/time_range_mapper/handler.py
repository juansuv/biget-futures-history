import json
import time
from typing import Dict, Any, List
from datetime import datetime, timedelta

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Time Range Mapper Lambda: Divide 8 años de historial en ventanas de 6 meses
    para procesamiento paralelo de búsqueda de símbolos
    """
    try:
        print("Time Range Mapper lambda invoked")
        
        # Configuración de rangos de tiempo
        end_time = int(time.time() * 1000)  # Ahora en milisegundos
        start_time = end_time - (9 * 365 * 24 * 60 * 60 * 1000)  # 8 años atrás
        
        # Tamaño de ventana: 3 meses para mayor paralelismo
        window_size_ms = 3 * 30 * 24 * 60 * 60 * 1000  # 3 meses en milisegundos
        
        # Generar ventanas de tiempo
        time_windows = []
        current_start = start_time
        window_id = 1
        
        while current_start < end_time:
            current_end = min(current_start + window_size_ms - 1, end_time)
            
            # Crear ventana con metadatos
            window = {
                "window_id": window_id,
                "start_time": current_start,
                "end_time": current_end,
                "start_date": datetime.fromtimestamp(current_start / 1000).isoformat(),
                "end_date": datetime.fromtimestamp(current_end / 1000).isoformat(),
                "duration_days": (current_end - current_start) / (24 * 60 * 60 * 1000)
            }
            
            time_windows.append(window)
            current_start = current_end + 1
            window_id += 1
        
        print(f"Generated {len(time_windows)} time windows of ~6 months each")
        print(f"Time range: {datetime.fromtimestamp(start_time / 1000).isoformat()} to {datetime.fromtimestamp(end_time / 1000).isoformat()}")
        
        # Resultado para el Step Function
        result = {
            'statusCode': 200,
            'message': f'Generated {len(time_windows)} time windows for parallel symbol search',
            'time_windows': time_windows,
            'total_windows': len(time_windows),
            'total_years': 8,
            'window_size_months': 6
        }
        
        return result
        
    except Exception as e:
        print(f"Error in time range mapper: {e}")
        return {
            'statusCode': 500,
            'error': str(e),
            'message': 'Error generating time windows'
        }