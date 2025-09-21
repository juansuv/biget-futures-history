import json
import os
import boto3
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import orjson

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Analytics Processor Lambda: Análisis estadístico simplificado (sin gráficos)
    """
    try:
        print("📊 Starting statistical analysis (simple version)...")
        
        # Obtener parámetros del evento
        analysis_type = event.get('analysis_type', 'full')
        execution_name = event.get('execution_name')
        days_back = event.get('days_back', 30)
        
        # Cargar datos desde S3
        orders_data = load_orders_from_s3(execution_name)
        if not orders_data:
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'No orders data found'})
            }
        
        print(f"📈 Loaded {len(orders_data)} orders for analysis")
        
        # Convertir a DataFrame de pandas
        df = prepare_dataframe(orders_data)
        if df.empty:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'No valid orders for analysis'})
            }
        
        # Filtrar por fecha si se especifica
        if days_back:
            cutoff_date = datetime.now() - timedelta(days=days_back)
            df = df[df['date'] >= cutoff_date]
            print(f"📅 Filtered to last {days_back} days: {len(df)} orders")
        
        # Realizar análisis
        analysis_results = {}
        
        # Resumen por símbolo
        analysis_results['symbol_summary'] = generate_symbol_summary(df)
        
        # Top 15 PnL
        analysis_results['top_15_pnl'] = get_top_15_pnl(df)
        
        # PnL diario y acumulado
        analysis_results['daily_pnl'] = calculate_daily_pnl(df)
        analysis_results['cumulative_pnl'] = calculate_cumulative_pnl(df)
        
        # Análisis básico de correlaciones
        analysis_results['correlations'] = calculate_correlations(df)
        
        # Estadísticas generales
        analysis_results['general_stats'] = calculate_general_stats(df)
        
        # Guardar resultados en S3
        s3_result = save_analysis_to_s3(analysis_results, execution_name)
        
        # Preparar respuesta
        response = {
            'message': 'Statistical analysis completed successfully',
            'analysis_type': analysis_type,
            'orders_analyzed': len(df),
            'date_range': {
                'from': df['date'].min().isoformat() if not df.empty else None,
                'to': df['date'].max().isoformat() if not df.empty else None
            },
            'summary_stats': {
                'total_trades': len(df),
                'unique_symbols': df['symbol'].nunique() if 'symbol' in df.columns else 0,
                'total_volume': float(df['filledAmount'].sum()) if 'filledAmount' in df.columns else 0,
                'total_pnl': float(df['pnl_net'].sum()) if 'pnl_net' in df.columns else 0,
                'win_rate': float((df['is_win'].sum() / len(df) * 100)) if 'is_win' in df.columns and len(df) > 0 else 0
            }
        }
        
        if s3_result:
            response.update(s3_result)
            
        return {
            'statusCode': 200,
            'body': json.dumps(response, default=str)
        }
        
    except Exception as e:
        print(f"❌ Error in analytics processor: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': 'Error in statistical analysis'
            })
        }


def load_orders_from_s3(execution_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """Cargar órdenes desde S3 para análisis"""
    try:
        s3_client = boto3.client('s3')
        bucket_name = os.environ.get('RESULTS_BUCKET')
        
        if not bucket_name:
            print("❌ RESULTS_BUCKET not configured")
            return []
            
        # Buscar el archivo de resultados más reciente o específico
        if execution_name:
            prefix = f"results/"
            response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
            
            if 'Contents' in response:
                matching_files = [
                    obj for obj in response['Contents'] 
                    if execution_name in obj['Key'] and obj['Key'].endswith('.json')
                ]
                if matching_files:
                    latest_file = max(matching_files, key=lambda x: x['LastModified'])
                    s3_key = latest_file['Key']
                else:
                    print(f"No file found for execution: {execution_name}")
                    return []
            else:
                print("No files found in results folder")
                return []
        else:
            # Tomar el archivo más reciente
            response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix="results/")
            if 'Contents' in response and response['Contents']:
                latest_file = max(response['Contents'], key=lambda x: x['LastModified'])
                s3_key = latest_file['Key']
            else:
                print("No result files found")
                return []
        
        print(f"📥 Loading orders from s3://{bucket_name}/{s3_key}")
        
        # Cargar archivo
        file_response = s3_client.get_object(Bucket=bucket_name, Key=s3_key)
        content = file_response['Body'].read()
        
        try:
            data = orjson.loads(content)
        except:
            data = json.loads(content)
        
        return data.get('orders', [])
        
    except Exception as e:
        print(f"❌ Error loading orders from S3: {e}")
        return []


def prepare_dataframe(orders_data: List[Dict[str, Any]]) -> pd.DataFrame:
    """Convertir datos de órdenes a DataFrame optimizado"""
    try:
        if not orders_data:
            return pd.DataFrame()
            
        df = pd.DataFrame(orders_data)
        
        # Convertir tipos numéricos
        numeric_columns = ['size', 'filledAmount', 'fee', 'price', 'avgPrice', 'cTime', 'uTime']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Convertir timestamps
        if 'cTime' in df.columns:
            df['date'] = pd.to_datetime(df['cTime'], unit='ms', errors='coerce')
            df['date_only'] = df['date'].dt.date
        
        # Calcular PnL
        if 'filledAmount' in df.columns and 'avgPrice' in df.columns:
            df['trade_value'] = df['filledAmount'] * df['avgPrice']
        
        if 'fee' in df.columns:
            df['fee'] = df['fee'].fillna(0)
            # Simplificado: asumir que filledAmount es el valor de PnL bruto
            df['pnl_gross'] = df.get('trade_value', 0)
            df['pnl_net'] = df['pnl_gross'] - df['fee']
        else:
            df['pnl_net'] = df.get('trade_value', 0)
        
        # Side por defecto
        if 'side' not in df.columns:
            df['side'] = 'unknown'
        
        # Win rate
        df['is_win'] = df['pnl_net'] > 0
        
        print(f"✅ DataFrame prepared: {len(df)} rows")
        return df.dropna(subset=['symbol', 'date'] if 'symbol' in df.columns else ['date'])
        
    except Exception as e:
        print(f"❌ Error preparing DataFrame: {e}")
        return pd.DataFrame()


def generate_symbol_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """Generar resumen estadístico por símbolo"""
    try:
        if df.empty or 'symbol' not in df.columns:
            return {}
            
        symbol_stats = df.groupby('symbol').agg({
            'symbol': 'count',
            'filledAmount': 'sum',
            'pnl_net': 'sum',
            'fee': 'sum',
            'is_win': ['sum', 'count']
        }).round(4)
        
        # Flatten columns
        symbol_stats.columns = ['trades', 'volume', 'pnl_net', 'fees', 'wins', 'total_trades']
        
        # Win rate
        symbol_stats['win_rate'] = (symbol_stats['wins'] / symbol_stats['total_trades'] * 100).round(2)
        
        # Sort by PnL
        symbol_stats = symbol_stats.sort_values('pnl_net', ascending=False)
        
        print(f"📈 Generated summary for {len(symbol_stats)} symbols")
        return symbol_stats.to_dict('index')
        
    except Exception as e:
        print(f"❌ Error generating symbol summary: {e}")
        return {}


def get_top_15_pnl(df: pd.DataFrame) -> Dict[str, Any]:
    """Top 15 símbolos por PnL neto"""
    try:
        if df.empty or 'symbol' not in df.columns:
            return {}
            
        top_15 = df.groupby('symbol')['pnl_net'].sum().sort_values(ascending=False).head(15)
        
        return {
            'symbols': top_15.index.tolist(),
            'pnl_values': top_15.values.tolist(),
            'total_pnl': float(top_15.sum())
        }
        
    except Exception as e:
        print(f"❌ Error calculating top 15 PnL: {e}")
        return {}


def calculate_daily_pnl(df: pd.DataFrame) -> Dict[str, Any]:
    """Calcular PnL diario"""
    try:
        if df.empty or 'date_only' not in df.columns:
            return {}
            
        daily_pnl = df.groupby('date_only')['pnl_net'].sum().sort_index()
        
        return {
            'dates': [d.isoformat() for d in daily_pnl.index],
            'daily_pnl': daily_pnl.values.tolist(),
            'total_days': len(daily_pnl),
            'avg_daily_pnl': float(daily_pnl.mean()),
            'best_day': float(daily_pnl.max()),
            'worst_day': float(daily_pnl.min()),
            'positive_days': int((daily_pnl > 0).sum()),
            'negative_days': int((daily_pnl < 0).sum())
        }
        
    except Exception as e:
        print(f"❌ Error calculating daily PnL: {e}")
        return {}


def calculate_cumulative_pnl(df: pd.DataFrame) -> Dict[str, Any]:
    """Calcular PnL acumulado con drawdowns"""
    try:
        if df.empty or 'date_only' not in df.columns:
            return {}
            
        daily_pnl = df.groupby('date_only')['pnl_net'].sum().sort_index()
        cumulative_pnl = daily_pnl.cumsum()
        
        # Drawdown calculation
        running_max = cumulative_pnl.expanding().max()
        drawdown = cumulative_pnl - running_max
        max_drawdown = float(drawdown.min())
        
        return {
            'dates': [d.isoformat() for d in cumulative_pnl.index],
            'cumulative_pnl': cumulative_pnl.values.tolist(),
            'final_pnl': float(cumulative_pnl.iloc[-1]) if len(cumulative_pnl) > 0 else 0,
            'max_drawdown': max_drawdown,
            'peak_pnl': float(cumulative_pnl.max()),
            'drawdown_percentage': round((max_drawdown / cumulative_pnl.max() * 100), 2) if cumulative_pnl.max() > 0 else 0
        }
        
    except Exception as e:
        print(f"❌ Error calculating cumulative PnL: {e}")
        return {}


def calculate_correlations(df: pd.DataFrame) -> Dict[str, Any]:
    """Calcular correlaciones básicas"""
    try:
        if df.empty:
            return {}
            
        correlations = {}
        
        # Correlaciones principales
        if 'filledAmount' in df.columns and 'pnl_net' in df.columns:
            correlations['volume_vs_pnl'] = float(df['filledAmount'].corr(df['pnl_net']))
        
        if 'fee' in df.columns and 'pnl_net' in df.columns:
            correlations['fee_vs_pnl'] = float(df['fee'].corr(df['pnl_net']))
        
        # Trend analysis - PnL over time
        if 'date' in df.columns and 'pnl_net' in df.columns:
            df['day_number'] = (df['date'] - df['date'].min()).dt.days
            correlations['time_vs_pnl'] = float(df['day_number'].corr(df['pnl_net']))
        
        return correlations
        
    except Exception as e:
        print(f"❌ Error calculating correlations: {e}")
        return {}


def calculate_general_stats(df: pd.DataFrame) -> Dict[str, Any]:
    """Estadísticas generales del trading"""
    try:
        if df.empty:
            return {}
        
        stats = {}
        
        # Estadísticas básicas
        stats['total_trades'] = len(df)
        stats['unique_symbols'] = df['symbol'].nunique() if 'symbol' in df.columns else 0
        
        if 'filledAmount' in df.columns:
            stats['total_volume'] = float(df['filledAmount'].sum())
            stats['avg_trade_size'] = float(df['filledAmount'].mean())
            stats['max_trade_size'] = float(df['filledAmount'].max())
            stats['min_trade_size'] = float(df['filledAmount'].min())
        
        if 'pnl_net' in df.columns:
            stats['total_pnl'] = float(df['pnl_net'].sum())
            stats['avg_pnl_per_trade'] = float(df['pnl_net'].mean())
            stats['best_trade'] = float(df['pnl_net'].max())
            stats['worst_trade'] = float(df['pnl_net'].min())
        
        if 'is_win' in df.columns:
            stats['winning_trades'] = int(df['is_win'].sum())
            stats['losing_trades'] = int((~df['is_win']).sum())
            stats['win_rate'] = float(df['is_win'].mean() * 100)
        
        if 'fee' in df.columns:
            stats['total_fees'] = float(df['fee'].sum())
            stats['avg_fee_per_trade'] = float(df['fee'].mean())
        
        # Distribución por lado (si existe)
        if 'side' in df.columns:
            side_counts = df['side'].value_counts().to_dict()
            stats['side_distribution'] = {k: int(v) for k, v in side_counts.items()}
        
        return stats
        
    except Exception as e:
        print(f"❌ Error calculating general stats: {e}")
        return {}


def save_analysis_to_s3(analysis_results: Dict[str, Any], execution_name: Optional[str] = None) -> Dict[str, Any]:
    """Guardar resultados de análisis en S3"""
    try:
        s3_client = boto3.client('s3')
        bucket_name = os.environ.get('RESULTS_BUCKET')
        
        if not bucket_name:
            print("❌ RESULTS_BUCKET not configured")
            return {}
        
        timestamp = int(datetime.now().timestamp())
        execution_id = execution_name if execution_name else 'analytics'
        s3_key = f"analytics/{timestamp}_{execution_id}_analysis.json"
        
        # Preparar datos
        analysis_data = {
            'timestamp': timestamp,
            'execution_name': execution_name,
            'analysis_results': analysis_results,
            'generated_at': datetime.now().isoformat()
        }
        
        # Usar orjson para serialización rápida
        json_body = orjson.dumps(analysis_data, option=orjson.OPT_INDENT_2)
        
        # Guardar en S3
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=json_body,
            ContentType='application/json',
            ServerSideEncryption='AES256'
        )
        
        public_url = f"https://{bucket_name}.s3.amazonaws.com/{s3_key}"
        
        print(f"💾 Analysis saved to s3://{bucket_name}/{s3_key}")
        
        return {
            'analysis_s3_key': s3_key,
            'analysis_url': public_url
        }
        
    except Exception as e:
        print(f"❌ Error saving analysis to S3: {e}")
        return {}