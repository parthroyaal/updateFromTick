import websocket
import json
import pandas as pd
from flask import Flask, render_template_string
from flask_socketio import SocketIO
from datetime import datetime, timedelta
import threading

app = Flask(__name__)
socketio = SocketIO(app)

class ChartData:
    def __init__(self, interval: timedelta):
        self._current_bar = None
        self._bar_start_time = None
        self.interval = interval
        self.data = []

    def _round_to_nearest_interval(self, time: datetime):
        seconds = int(time.timestamp())
        rounded_seconds = (seconds // int(self.interval.total_seconds())) * int(self.interval.total_seconds())
        return datetime.fromtimestamp(rounded_seconds)

    def update_from_tick(self, tick_time: datetime, price: float):
        rounded_time = self._round_to_nearest_interval(tick_time)

        if self._bar_start_time is None or rounded_time >= self._bar_start_time + self.interval:
            if self._current_bar is not None:
                self.data.append(self._current_bar)
            self._bar_start_time = rounded_time
            self._current_bar = {
                'time': self._bar_start_time.timestamp(),
                'open': price,
                'high': price,
                'low': price,
                'close': price
            }
        else:
            self._current_bar['high'] = max(self._current_bar['high'], price)
            self._current_bar['low'] = min(self._current_bar['low'], price)
            self._current_bar['close'] = price

        return self._current_bar

timeframes = {
    '1s': timedelta(seconds=1),
    '5s': timedelta(seconds=5),
    '15s': timedelta(seconds=15),
    '30s': timedelta(seconds=30),
    '1m': timedelta(minutes=1),
    '5m': timedelta(minutes=5),
    '15m': timedelta(minutes=15),
    '30m': timedelta(minutes=30),
    '1h': timedelta(hours=1),
    '4h': timedelta(hours=4),
}

chart_data = {tf: ChartData(interval) for tf, interval in timeframes.items()}

ws_url = "wss://stream.bybit.com/v5/public/linear"

def on_message(ws, message):
    tick = json.loads(message)
    if tick.get('topic') == 'publicTrade.BTCUSDT':
        trade_data = tick['data'][0]
        tick_time = datetime.fromtimestamp(trade_data['T'] / 1000)
        price = float(trade_data['p'])
        
        for tf, data in chart_data.items():
            updated_bar = data.update_from_tick(tick_time, price)
            socketio.emit(f'update_chart_{tf}', updated_bar)

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
    <title>Real-time Multi-timeframe Candlestick Chart</title>
    <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        #chart-container { width: 1300px; height: 550px; }
        .timeframe-button { margin: 5px; }
    </style>
</head>
<body>
    <div id="timeframe-buttons">
        {% for tf in timeframes %}
            <button class="timeframe-button" data-timeframe="{{ tf }}">{{ tf }}</button>
        {% endfor %}
    </div>
    <div id="chart-container"></div>
    <script>
        const chart = LightweightCharts.createChart(document.getElementById('chart-container'), {
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

        const candleSeries = {};
        const timeframes = {{ timeframes|tojson }};
        let currentTimeframe = '1m';

        // Create a series for each timeframe
        timeframes.forEach(tf => {
            candleSeries[tf] = chart.addCandlestickSeries();
            if (tf !== currentTimeframe) {
                candleSeries[tf].applyOptions({
                    visible: false
                });
            }
        });

        const socket = io();

        function loadChartData(timeframe) {
            fetch(`/get_data/${timeframe}`)
                .then(response => response.json())
                .then(data => {
                    candleSeries[timeframe].setData(data);
                });
        }

        function switchTimeframe(newTimeframe) {
            candleSeries[currentTimeframe].applyOptions({
                visible: false
            });
            candleSeries[newTimeframe].applyOptions({
                visible: true
            });
            currentTimeframe = newTimeframe;
            loadChartData(currentTimeframe);
        }

        document.querySelectorAll('.timeframe-button').forEach(button => {
            button.addEventListener('click', () => {
                const timeframe = button.getAttribute('data-timeframe');
                switchTimeframe(timeframe);
            });
        });

        // Load initial data for all timeframes
        timeframes.forEach(tf => loadChartData(tf));

        // Listen for updates on all timeframes
        timeframes.forEach(tf => {
            socket.on(`update_chart_${tf}`, function(newBar) {
                candleSeries[tf].update(newBar);
            });
        });
    </script>
</body>
</html>
    """
    return render_template_string(html_template, timeframes=list(timeframes.keys()))

@app.route('/get_data/<timeframe>')
def get_data(timeframe):
    if timeframe in chart_data:
        return json.dumps(chart_data[timeframe].data)
    return json.dumps([])

if __name__ == '__main__':
    ws = websocket.WebSocketApp(ws_url,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close,
                                on_open=on_open)
    
    wst = threading.Thread(target=ws.run_forever)
    wst.daemon = True
    wst.start()
    
    socketio.run(app, debug=True, use_reloader=False)