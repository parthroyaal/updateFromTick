import websocket
import json
import pandas as pd
from flask import Flask, render_template_string
from flask_socketio import SocketIO
from datetime import datetime, timedelta

app = Flask(__name__)
socketio = SocketIO(app)

class ChartData:
    def __init__(self):
        self._last_bar = None
        self._current_bar = None
        self._bar_start_time = None

    def _series_datetime_format(self, series: pd.Series):
        series['time'] = pd.to_datetime(series['time'])
        return series

    def update_from_tick(self, series: pd.Series):
        """Updates the data from a tick."""
        series = self._series_datetime_format(series)
        current_time = series['time']

        if self._bar_start_time is None or current_time >= self._bar_start_time + timedelta(seconds=5):
            # Start a new bar
            self._bar_start_time = current_time.replace(microsecond=0)
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

chart_data = ChartData()

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
        <title>Real-time Candlestick Chart</title>
        <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    </head>
    <body>
        <div id="chart" style="width: 800px; height: 400px;"></div>
        <script>
            const chart = LightweightCharts.createChart(document.getElementById('chart'), {
                width: 800,
                height: 400,
                rightPriceScale: {
                    borderVisible: false,
                },
                timeScale: {
                    borderVisible: false,
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