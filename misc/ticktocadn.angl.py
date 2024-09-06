from SmartApi import SmartConnect
import pyotp
from logzero import logger
from SmartApi.smartWebSocketV2 import SmartWebSocketV2
import pandas as pd
from lightweight_charts import Chart
from time import sleep
import json

# API credentials and initialization
api_key = 'nBgBs7Ku'
username = 'P547740'
pwd = '8894'
smartApi = SmartConnect(api_key)

try:
    token = "T2PX34ABOGB3VZIVENMUAOJ5PQ"
    totp = pyotp.TOTP(token).now()
except Exception as e:
    logger.error("Invalid Token: The provided token is not valid.")
    raise e

correlation_id = "abcde"
data = smartApi.generateSession(username, pwd, totp)

if data['status'] == False:
    logger.error(data)
else:
    authToken = data['data']['jwtToken']
    refreshToken = data['data']['refreshToken']
    feedToken = smartApi.getfeedToken()
    res = smartApi.getProfile(refreshToken)
    smartApi.generateToken(refreshToken)
    res = res['data']['exchanges']

# WebSocket configuration
AUTH_TOKEN = authToken
API_KEY = api_key
CLIENT_CODE = username
FEED_TOKEN = feedToken
correlation_id = "abc123"
action = 1
mode = 1
token_list = [
    {
        "exchangeType": 1,
        "tokens": ["99926000"]
    }
]

sws = SmartWebSocketV2(AUTH_TOKEN, API_KEY, CLIENT_CODE, FEED_TOKEN, max_retry_attempt=2, retry_strategy=0, retry_delay=10, retry_duration=30)

# Global variables
tick_data_list = []
accumulated_ticks = []
chart = None

def setinit(dfx):
    global chart
    if chart is None:
        chart = Chart()
        # chart.layout(background_color='#ffffff', font_family='Trebuchet MS', font_size=16)
        chart.layout()
        chart.set(dfx)
        chart.show()

def convert_to_candlestick(df):
    if df is None or df.empty:
        return pd.DataFrame()

    df['time'] = pd.to_datetime(df['time'])
    df.set_index('time', inplace=True)
    df_resampled = df['price'].resample('5s').ohlc()  # Resample to 5-second intervals
    df_resampled.reset_index(inplace=True)
    return df_resampled

def handle_tick(message):
    global tick_data_list, accumulated_ticks, chart

    try:
        tick = message
        print(f"Ticks: {tick}")
        if 'last_traded_price' in tick:
            tick_time = pd.to_datetime(tick['exchange_timestamp'] / 1000, unit='s').strftime('%Y-%m-%d %H:%M:%S')
            tick_data = {'time': tick_time, 'price': tick['last_traded_price'] / 100}

            accumulated_ticks.append(tick_data)

            current_time = pd.to_datetime(tick_time)
            if len(accumulated_ticks) >= 5 or (len(accumulated_ticks) > 0 and (current_time - pd.to_datetime(accumulated_ticks[0]['time'])).seconds >= 5):
                tick_data_list.extend(accumulated_ticks)
                accumulated_ticks = []
                df = pd.DataFrame(tick_data_list)
                df_candlestick = convert_to_candlestick(df)

                if len(df_candlestick) > 0:
                    if chart is None and len(df_candlestick) >= 1:
                        setinit(df_candlestick)
                        print("Chart initialized")

                    if chart is not None:
                        last_candle = df_candlestick.iloc[-1]
                        chart.update(last_candle)
                        print(f"Updated chart with: {last_candle}")
            
        # # Save data locally every minute
        # if len(df_candlestick) % 60 == 0:
        #     df_candlestick.to_csv('candlestick_data.csv', index=False)

    except Exception as e:
        print(f"Unexpected error: {e}")

def on_data(wsapp, message):
    handle_tick(message)

def on_open(wsapp):
    logger.info("WebSocket connection opened")
    sws.subscribe(correlation_id, mode, token_list)

def on_error(wsapp, error):
    logger.error(f"WebSocket error: {error}")

def on_close(wsapp):
    logger.info("WebSocket connection closed")

def on_control_message(wsapp, message):
    logger.info(f"Control Message: {message}")

# Assign the callbacks
sws.on_open = on_open
sws.on_data = on_data
sws.on_error = on_error
sws.on_close = on_close
sws.on_control_message = on_control_message

# Connect to the WebSocket
sws.connect()

# Keep the script running to continue receiving WebSocket messages
while True:
    sleep(1)