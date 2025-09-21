import json
import os
import boto3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import base64
import io
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score
import matplotlib
matplotlib.use('Agg')  # For Lambda environment
import matplotlib.pyplot as plt

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Analytics Processor Lambda: Análisis estadístico completo de órdenes de trading
    """
    try:
        print("📊 Starting statistical analysis...")
        
        # Obtener parámetros del evento
        analysis_type = event.get('analysis_type', 'full')  # 'full', 'summary', 'pnl', 'charts'
        execution_name = event.get('execution_name')
        days_back = event.get('days_back', 30)  # Análisis de últimos N días
        
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
        
        # Realizar análisis según el tipo solicitado
        analysis_results = {}
        
        if analysis_type in ['full', 'summary']:
            analysis_results['symbol_summary'] = generate_symbol_summary(df)
            analysis_results['top_15_pnl'] = get_top_15_pnl(df)
            
        if analysis_type in ['full', 'pnl']:
            analysis_results['daily_pnl'] = calculate_daily_pnl(df)
            analysis_results['cumulative_pnl'] = calculate_cumulative_pnl(df)
            
        if analysis_type in ['full', 'regression']:
            analysis_results['regression_analysis'] = perform_regression_analysis(df)
            
        if analysis_type in ['full', 'charts']:
            analysis_results['charts'] = generate_charts(df)
            
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
                'total_pnl': float(df['pnl_net'].sum()) if 'pnl_net' in df.columns else 0
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
    """
    Cargar órdenes desde S3 para análisis
    """
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
                    # Tomar el más reciente
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
        data = json.loads(content)
        
        return data.get('orders', [])
        
    except Exception as e:
        print(f"❌ Error loading orders from S3: {e}")
        return []


def prepare_dataframe(orders_data: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Convertir datos de órdenes a DataFrame de pandas con columnas calculadas
    """
    try:
        if not orders_data:
            return pd.DataFrame()
            
        df = pd.DataFrame(orders_data)
        
        # Convertir tipos de datos
        numeric_columns = ['size', 'filledAmount', 'fee', 'price', 'avgPrice', 'cTime', 'uTime']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Convertir timestamps a datetime
        if 'cTime' in df.columns:
            df['date'] = pd.to_datetime(df['cTime'], unit='ms', errors='coerce')
            df['date_only'] = df['date'].dt.date
        
        # Calcular PnL bruto y neto
        if 'size' in df.columns and 'avgPrice' in df.columns:
            # PnL bruto = (precio_actual - precio_promedio) * cantidad para LONG
            # Para simplificar, asumimos que todas las órdenes son cerradas
            df['pnl_gross'] = df['filledAmount'] * df['avgPrice']  # Valor total
            
        if 'fee' in df.columns:
            df['fee'] = df['fee'].fillna(0)
            df['pnl_net'] = df.get('pnl_gross', 0) - df['fee']
        else:
            df['pnl_net'] = df.get('pnl_gross', 0)
        
        # Determinar side si no existe
        if 'side' not in df.columns:
            df['side'] = 'unknown'
        
        # Win rate calculation (simplificado)
        df['is_win'] = df['pnl_net'] > 0
        
        print(f"✅ DataFrame prepared: {len(df)} rows, {len(df.columns)} columns")
        print(f"📊 Columns: {list(df.columns)}")
        
        return df.dropna(subset=['symbol', 'date'] if 'symbol' in df.columns else ['date'])
        
    except Exception as e:
        print(f"❌ Error preparing DataFrame: {e}")
        return pd.DataFrame()


def generate_symbol_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Generar resumen estadístico por símbolo
    """
    try:
        if df.empty or 'symbol' not in df.columns:
            return {}
            
        symbol_stats = df.groupby('symbol').agg({
            'symbol': 'count',  # trades count
            'size': 'sum',      # total size
            'filledAmount': 'sum',  # total volume
            'pnl_gross': 'sum', # PnL bruto
            'fee': 'sum',       # total fees
            'pnl_net': 'sum',   # PnL neto
            'is_win': ['sum', 'count']  # wins and total for win rate
        }).round(4)
        
        # Flatten column names
        symbol_stats.columns = ['trades', 'total_size', 'volume', 'pnl_gross', 'fees', 'pnl_net', 'wins', 'total_trades']
        
        # Calculate win rate
        symbol_stats['win_rate'] = (symbol_stats['wins'] / symbol_stats['total_trades'] * 100).round(2)
        
        # Sort by PnL net descending
        symbol_stats = symbol_stats.sort_values('pnl_net', ascending=False)
        
        print(f"📈 Generated summary for {len(symbol_stats)} symbols")
        
        return symbol_stats.to_dict('index')
        
    except Exception as e:
        print(f"❌ Error generating symbol summary: {e}")
        return {}


def get_top_15_pnl(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Top 15 símbolos por PnL neto
    """
    try:
        if df.empty or 'symbol' not in df.columns:
            return {}
            
        top_15 = df.groupby('symbol')['pnl_net'].sum().sort_values(ascending=False).head(15)
        
        result = {
            'symbols': top_15.index.tolist(),
            'pnl_values': top_15.values.tolist(),
            'total_pnl': float(top_15.sum())
        }
        
        print(f"🏆 Top 15 PnL symbols calculated")
        return result
        
    except Exception as e:
        print(f"❌ Error calculating top 15 PnL: {e}")
        return {}


def calculate_daily_pnl(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calcular PnL diario
    """
    try:
        if df.empty or 'date_only' not in df.columns:
            return {}
            
        daily_pnl = df.groupby('date_only')['pnl_net'].sum().sort_index()
        
        result = {
            'dates': [d.isoformat() for d in daily_pnl.index],
            'daily_pnl': daily_pnl.values.tolist(),
            'total_days': len(daily_pnl),
            'avg_daily_pnl': float(daily_pnl.mean()),
            'best_day': float(daily_pnl.max()),
            'worst_day': float(daily_pnl.min())
        }
        
        print(f"📅 Daily PnL calculated for {len(daily_pnl)} days")
        return result
        
    except Exception as e:
        print(f"❌ Error calculating daily PnL: {e}")
        return {}


def calculate_cumulative_pnl(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calcular PnL acumulado
    """
    try:
        if df.empty or 'date_only' not in df.columns:
            return {}
            
        daily_pnl = df.groupby('date_only')['pnl_net'].sum().sort_index()
        cumulative_pnl = daily_pnl.cumsum()
        
        # Calcular drawdown
        running_max = cumulative_pnl.expanding().max()
        drawdown = cumulative_pnl - running_max
        max_drawdown = float(drawdown.min())
        
        result = {
            'dates': [d.isoformat() for d in cumulative_pnl.index],
            'cumulative_pnl': cumulative_pnl.values.tolist(),
            'final_pnl': float(cumulative_pnl.iloc[-1]) if len(cumulative_pnl) > 0 else 0,
            'max_drawdown': max_drawdown,
            'drawdown_series': drawdown.values.tolist()
        }
        
        print(f"📈 Cumulative PnL calculated")
        return result
        
    except Exception as e:
        print(f"❌ Error calculating cumulative PnL: {e}")
        return {}


def perform_regression_analysis(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Realizar análisis de regresión
    """
    try:
        if df.empty or 'date' not in df.columns:
            return {}
            
        # Preparar datos para regresión
        df_reg = df.copy()
        df_reg['day_number'] = (df_reg['date'] - df_reg['date'].min()).dt.days
        
        # PnL vs tiempo (tendencia temporal)
        daily_pnl = df_reg.groupby('day_number')['pnl_net'].sum().reset_index()
        
        if len(daily_pnl) < 2:
            return {'error': 'Insufficient data for regression'}
        
        X = daily_pnl[['day_number']]
        y = daily_pnl['pnl_net']
        
        # Regresión lineal
        model = LinearRegression()
        model.fit(X, y)
        y_pred = model.predict(X)
        
        r2 = r2_score(y, y_pred)
        slope = float(model.coef_[0])
        intercept = float(model.intercept_)
        
        # Análisis de correlaciones
        correlations = {}
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 1:
            corr_matrix = df[numeric_cols].corr()
            correlations = {
                'size_vs_pnl': float(corr_matrix.loc['size', 'pnl_net']) if 'size' in corr_matrix.columns and 'pnl_net' in corr_matrix.columns else None,
                'volume_vs_pnl': float(corr_matrix.loc['filledAmount', 'pnl_net']) if 'filledAmount' in corr_matrix.columns and 'pnl_net' in corr_matrix.columns else None
            }
        
        result = {
            'temporal_trend': {
                'slope': slope,
                'intercept': intercept,
                'r_squared': float(r2),
                'interpretation': 'positive_trend' if slope > 0 else 'negative_trend'
            },
            'correlations': correlations,
            'regression_data': {
                'x_values': daily_pnl['day_number'].tolist(),
                'y_actual': daily_pnl['pnl_net'].tolist(),
                'y_predicted': y_pred.tolist()
            }
        }
        
        print(f"📊 Regression analysis completed (R²={r2:.3f})")
        return result
        
    except Exception as e:
        print(f"❌ Error in regression analysis: {e}")
        return {}


def generate_charts(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Generar gráficos como imágenes base64
    """
    try:
        charts = {}
        
        # Configurar estilo básico
        plt.style.use('default')
        plt.rcParams['figure.facecolor'] = 'white'
        
        # 1. PnL acumulado por día
        if 'date_only' in df.columns and 'pnl_net' in df.columns:
            daily_pnl = df.groupby('date_only')['pnl_net'].sum().sort_index()
            cumulative_pnl = daily_pnl.cumsum()
            
            plt.figure(figsize=(12, 6))
            plt.plot(cumulative_pnl.index, cumulative_pnl.values, linewidth=2, marker='o', markersize=4)
            plt.title('PnL Neto Acumulado por Día', fontsize=16, fontweight='bold')
            plt.xlabel('Fecha')
            plt.ylabel('PnL Acumulado')
            plt.grid(True, alpha=0.3)
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            charts['cumulative_pnl'] = plot_to_base64()
            plt.close()
        
        # 2. Top 15 símbolos por PnL
        if 'symbol' in df.columns and 'pnl_net' in df.columns:
            top_15 = df.groupby('symbol')['pnl_net'].sum().sort_values(ascending=True).tail(15)
            
            plt.figure(figsize=(12, 8))
            bars = plt.barh(range(len(top_15)), top_15.values)
            plt.yticks(range(len(top_15)), top_15.index)
            plt.title('Top 15 Símbolos por PnL Neto', fontsize=16, fontweight='bold')
            plt.xlabel('PnL Neto')
            
            # Colorear barras según positivo/negativo
            for i, bar in enumerate(bars):
                if top_15.values[i] >= 0:
                    bar.set_color('green')
                else:
                    bar.set_color('red')
            
            plt.grid(True, alpha=0.3, axis='x')
            plt.tight_layout()
            
            charts['top_15_pnl'] = plot_to_base64()
            plt.close()
        
        # 3. Histograma de tamaños de orden
        if 'size' in df.columns:
            plt.figure(figsize=(10, 6))
            plt.hist(df['size'].dropna(), bins=50, alpha=0.7, edgecolor='black')
            plt.title('Distribución de Tamaños de Orden', fontsize=16, fontweight='bold')
            plt.xlabel('Tamaño de Orden')
            plt.ylabel('Frecuencia')
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            
            charts['size_distribution'] = plot_to_base64()
            plt.close()
        
        print(f"📊 Generated {len(charts)} charts")
        return charts
        
    except Exception as e:
        print(f"❌ Error generating charts: {e}")
        return {}


def plot_to_base64() -> str:
    """
    Convertir plot actual a string base64
    """
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
    buffer.seek(0)
    image_png = buffer.getvalue()
    buffer.close()
    
    graphic = base64.b64encode(image_png)
    return graphic.decode('utf-8')


def save_analysis_to_s3(analysis_results: Dict[str, Any], execution_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Guardar resultados de análisis en S3
    """
    try:
        s3_client = boto3.client('s3')
        bucket_name = os.environ.get('RESULTS_BUCKET')
        
        if not bucket_name:
            print("❌ RESULTS_BUCKET not configured")
            return {}
        
        timestamp = int(datetime.now().timestamp())
        execution_id = execution_name if execution_name else 'analytics'
        s3_key = f"analytics/{timestamp}_{execution_id}_analysis.json"
        
        # Preparar datos para guardar
        analysis_data = {
            'timestamp': timestamp,
            'execution_name': execution_name,
            'analysis_results': analysis_results,
            'generated_at': datetime.now().isoformat()
        }
        
        # Guardar en S3
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=json.dumps(analysis_data, indent=2, default=str),
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