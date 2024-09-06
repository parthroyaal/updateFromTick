import pandas as pd
import websocket
import json
from lightweight_charts import Chart
from time import sleep

# WebSocket URL for Bybit Linear Futures
WEBSOCKET_URL = "wss://stream.bybit.com/v5/public/linear"

# Placeholder for tick data
tick_data_list = []
accumulated_ticks = []

# Initialize the chart
chart = None

def setinit(dfx):
    global chart
    if chart is None:
        chart = Chart()
        chart.layout(background_color='#f2f2f2', font_family='Trebuchet MS', font_size = 16)
        chart.set(dfx)
        chart.show()

def convert_to_candlestick(df):
    if df is None or df.empty:
        return pd.DataFrame()

    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)
    df_resampled = df['price'].resample('1S').ohlc()  # Resample to 5-second intervals
    df_resampled.reset_index(inplace=True)
    return df_resampled

def on_message(ws, message):
    global tick_data_list, accumulated_ticks, chart
    tick = json.loads(message)

    # Check for trade data in Bybit format
    if tick.get('topic') == 'publicTrade.BTCUSDT':
        trade_data = tick['data'][0]  # Assuming the data is in the first element
        print(trade_data)
        tick_time = pd.to_datetime(trade_data['T'] / 1000, unit='s').strftime('%Y-%m-%d %H:%M:%S')
        tick_data = {'time': tick_time, 'price': float(trade_data['p'])}

        # Accumulate tick data
        accumulated_ticks.append(tick_data)

        # Every 5 seconds, update the DataFrame and chart
        current_time = pd.to_datetime(tick_time)
        if len(accumulated_ticks) >= 5 or (len(accumulated_ticks) > 0 and (current_time - pd.to_datetime(accumulated_ticks[0]['time'])).seconds >= 5):
            # Append accumulated ticks to the main tick data list
            tick_data_list.extend(accumulated_ticks)

            # Clear accumulated ticks
            accumulated_ticks = []

            # Create a DataFrame for the tick data
            df = pd.DataFrame(tick_data_list)

            # Convert to candlestick format
            df_candlestick = convert_to_candlestick(df)

            if len(df_candlestick) > 0:
                # Initialize chart with the first candle if not already done
                if chart is None and len(df_candlestick) >= 1:
                    setinit(df_candlestick)

                # Update the chart with the latest tick data
                if chart is not None:
                    # Use the latest 5 seconds tick data converted to candlestick
                    last_candle = df_candlestick.iloc[-1]
                    chart.update(last_candle)
                    print(last_candle)

def on_error(ws, error):
    print(f"Error: {error}")

def on_close(ws):
    print("WebSocket closed")

def on_open(ws):
    print("Bybit WebSocket Opened")
    # Subscribe to a specific channel
    ws.send(json.dumps({"op": "subscribe", "args": ["publicTrade.BTCUSDT"]}))

# Initialize WebSocket
ws = websocket.WebSocketApp(WEBSOCKET_URL,
                            on_open=on_open,
                            on_message=on_message,
                            on_error=on_error,
                            on_close=on_close)

# Run WebSocket synchronously
ws.run_forever()

# # Keep the script running to continue receiving WebSocket messages
# while True:
#     sleep(1)
