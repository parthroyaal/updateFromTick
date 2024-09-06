from flask import Flask, render_template, request, url_for
import os
import pandas as pd
from datetime import timedelta
import numpy as np
import ta

app = Flask(__name__)

# Define the root directory
ROOT = "/home/acer/Videos/2024dir/00Jul19/data/data"

def calculate_indicators(df):
    """
    Calculates technical indicators for a given DataFrame.
    """
    df = df.copy()  # Avoid modifying the original DataFrame

    # Calculate moving averages (SMA)
    df['sma_12'] = ta.trend.sma_indicator(df['close'], window=12, fillna=False)
    df['sma_24'] = ta.trend.sma_indicator(df['close'], window=24, fillna=False)
    df['sma_50'] = ta.trend.sma_indicator(df['close'], window=50, fillna=False)
    df['sma_200'] = ta.trend.sma_indicator(df['close'], window=200, fillna=False)

    # Calculate RSI
    df['rsi'] = ta.momentum.rsi(df['close'], window=14, fillna=False)

    # Calculate MACD
    df['macd'] = ta.trend.macd(df['close'], window_slow=26, window_fast=12, fillna=False)
    df['macd_signal'] = ta.trend.macd_signal(df['close'], window_slow=26, window_fast=12, window_sign=9, fillna=False)
    df['macd_histogram'] = ta.trend.macd_diff(df['close'], window_slow=26, window_fast=12, window_sign=9, fillna=False)

    # Calculate VWAP
    if 'volume' in df.columns and df['volume'].sum() > 0:
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        df['vwap'] = (typical_price * df['volume']).rolling(window=14).sum() / df['volume'].rolling(window=14).sum()
    else:
        df['vwap'] = np.nan  # Use NaN for VWAP if volume is not available

    return df

def resample_and_indicators(df, timeframe):
    try:
        df['time'] = pd.to_datetime(df['time'])
        df.set_index('time', inplace=True)
        
        resampled = df.resample(timeframe).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
        
        # Calculate indicators
        resampled = calculate_indicators(resampled)
        
        resampled.reset_index(inplace=True)
        resampled['time'] = resampled['time'].astype(int) // 10**9  # Unix timestamp
        
        return resampled
    except Exception as e:
        print(f"Error in resample_and_indicators: {e}")
        print(f"DataFrame info:\n{df.info()}")
        raise

@app.route('/', methods=['GET', 'POST'])
def index():
    csv_files = ['None'] + [f for f in os.listdir(ROOT) if f.endswith('.csv')]
    
    selected_csvs = {
        'main_chart': request.form.get('main_chart_csv', 'None'),
        'chart_2': request.form.get('chart_2_csv', 'None'),
        'chart_3': request.form.get('chart_3_csv', 'None')
    }

    timeframe = request.form.get('timeframe', '5S')

    chart_data = {
        'main_chart': None,
        'chart_2': None,
        'chart_3': None
    }

    for chart, selected_csv in selected_csvs.items():
        if selected_csv != 'None':
            csv_path = os.path.join(ROOT, selected_csv)
            df = pd.read_csv(csv_path)

            required_columns = ['time', 'open', 'high', 'low', 'close', 'volume']
            if all(col in df.columns for col in required_columns):
                # Apply resampling and calculate indicators
                resampled_df = resample_and_indicators(df, timeframe)
                chart_data[chart] = resampled_df.to_dict('records')

    return render_template("index.html", 
                           csv_files=csv_files,
                           selected_csvs=selected_csvs,
                           timeframe=timeframe,
                           chart_data=chart_data)

if __name__ == '__main__':
    app.run(debug=True)
