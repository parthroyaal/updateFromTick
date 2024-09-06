import websocket
import json
import pandas as pd
from flask import Flask, render_template_string
from flask_socketio import SocketIO
from datetime import datetime, timedelta

app = Flask(__name__)
socketio = SocketIO(app)


import pandas as pd
import json
from datetime import datetime, timedelta

class ChartData:
    def __init__(self, interval: timedelta):
        """
        interval: timedelta object representing the time interval for the candlestick (e.g., 15 seconds, 1 minute)
        """
        self._last_bar = None
        self._current_bar = None
        self._bar_start_time = None
        self.interval = interval

    def _series_datetime_format(self, series: pd.Series):
        series['time'] = pd.to_datetime(series['time'])
        return series

    def _round_to_nearest_interval(self, time: datetime):
        # Round time down to the nearest interval
        seconds = int(time.timestamp())  # Convert to seconds
        rounded_seconds = (seconds // int(self.interval.total_seconds())) * int(self.interval.total_seconds())
        return datetime.fromtimestamp(rounded_seconds)

    def update_from_tick(self, series: pd.Series):
        """Updates the data from a tick."""
        series = self._series_datetime_format(series)
        current_time = series['time']

        # Round current time to the nearest interval boundary
        rounded_time = self._round_to_nearest_interval(current_time)

        # Create a new bar based on the interval
        if self._bar_start_time is None or rounded_time >= self._bar_start_time + self.interval:
            self._bar_start_time = rounded_time  # Use the rounded time for candlesticks
            self._current_bar = pd.Series({
                'time': self._bar_start_time.timestamp(),
                'open': series['price'],
                'high': series['price'],
                'low': series['price'],
                'close': series['price']
            })
            if self._last_bar is not None:
                yield self._last_bar.to_dict()
            self._last_bar = self._current_bar
        else:
            # Update current bar
            self._current_bar['high'] = max(self._current_bar['high'], series['price'])
            self._current_bar['low'] = min(self._current_bar['low'], series['price'])
            self._current_bar['close'] = series['price']

        yield self._current_bar.to_dict()





# 1 second  logic 
# chart_data_1sec = ChartData(interval=timedelta(seconds=1))


# 5second logic
# chart_data_5sec = ChartData(interval=timedelta(seconds=5))



# 15sec logic
# chart_data_15sec = ChartData(interval=timedelta(seconds=15))



# 30sec logic
# chart_data_30sec = ChartData(interval=timedelta(seconds=30))


# 1minute logic
chart_data_1min = ChartData(interval=timedelta(minutes=1))


# 3minute logic
#chart_data_3min = ChartData(interval=timedelta(minutes=3))


# 5minute logic
# chart_data_5min = ChartData(interval=timedelta(minutes=5))


# 15minute logic
# chart_data_15min = ChartData(interval=timedelta(minutes=15))


# 30minute logic
# chart_data_30min = ChartData(interval=timedelta(minutes=30))


# 1hour logic
# chart_data_1hour = ChartData(interval=timedelta(hours=1))


# 2hour logic
# chart_data_2hour = ChartData(interval=timedelta(hours=2))


# 4hour logic
# chart_data_4hour = ChartData(interval=timedelta(hours=4))


# 6hour logic
# chart_data_6hour = ChartData(interval=timedelta(hours=6))


# 8hour logic
# chart_data_8hour = ChartData(interval=timedelta(hours=8))


# 12hour logic 
# chart_data_12hour = ChartData(interval=timedelta(hours=12))


chart_data = chart_data_1min

ws_url = "wss://stream.bybit.com/v5/public/linear"

def on_message(ws, message):
    tick = json.loads(message)
    if tick.get('topic') == 'publicTrade.BTCUSDT':
        trade_data = tick['data'][0]
        tick_time = pd.to_datetime(trade_data['T'] / 1000, unit='s')
        tick_data = {'time': tick_time, 'price': float(trade_data['p'])}
        for updated_bar in chart_data.update_from_tick(pd.Series(tick_data)):
            socketio.emit('update_chart', updated_bar)

def on_error(ws, error):
    print(f"WebSocket Error: {error}")

def on_close(ws, close_status_code, close_msg):
    print(f"WebSocket Closed: {close_status_code} - {close_msg}")

def on_open(ws):
    print("Bybit WebSocket Opened")
    ws.send('{"op": "subscribe","args": ["publicTrade.BTCUSDT"]}')

@app.route('/')
def index():
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Real-time Candlestick Chart (1-minute)</title>
        <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    </head>
    <body>
        <div id="chart" style="width: 800px; height: 400px;"></div>
        <script>
            const chart = LightweightCharts.createChart(document.getElementById('chart'), {
                width: 1300,
                height: 550,
                rightPriceScale: {
                    borderVisible: true,
                },
                timeScale: {
                    borderVisible: true,
                    timeVisible: true,
                    secondsVisible: true,
                },
                grid: {
                    horzLines: {
                        color: '#eee',
                    },
                    vertLines: {
                        color: '#eee',
                    },
                },
            });
            const candleSeries = chart.addCandlestickSeries();
            
            const socket = io();
            socket.on('update_chart', function(newBar) {
                candleSeries.update(newBar);
            });
        </script>
    </body>
    </html>
    """
    return render_template_string(html_template)

if __name__ == '__main__':
    ws = websocket.WebSocketApp(ws_url,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close,
                                on_open=on_open)
    
    from threading import Thread
    wst = Thread(target=ws.run_forever)
    wst.daemon = True
    wst.start()
    
    socketio.run(app, debug=True, use_reloader=False)