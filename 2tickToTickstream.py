import websocket
import json
import pandas as pd
from flask import Flask, render_template_string, jsonify
from flask_socketio import SocketIO
from datetime import datetime, timedelta
import threading
import os

app = Flask(__name__)
socketio = SocketIO(app)

class ChartData:
    def __init__(self, interval: timedelta):
        self._last_bar = None
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

def save_data_to_csv():
    while True:
        for tf, data in chart_data.items():
            df = pd.DataFrame(data.data)
            if not df.empty:
                df['time'] = pd.to_datetime(df['time'], unit='s')
                df.to_csv(f'data_{tf}.csv', index=False)
        socketio.sleep(60)  # Save every minute

def load_data_from_csv():
    for tf, data in chart_data.items():
        file_name = f'data_{tf}.csv'
        if os.path.exists(file_name):
            df = pd.read_csv(file_name)
            df['time'] = pd.to_datetime(df['time']).astype(int) // 10**9
            data.data = df.to_dict('records')[-250:]  # Load last 250 candles

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

index_html = """
<!DOCTYPE html>
<html>
<head>
    <title>Real-time Multi-timeframe Candlestick Chart</title>
    <script src="https://unpkg.com/lightweight-charts/dist/lightweight-charts.standalone.production.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        #chart-container { width: 800px; height: 400px; }
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
            width: 800,
            height: 400,
            timeScale: {
                timeVisible: true,
                secondsVisible: true,
            },
        });
        const candleSeries = chart.addCandlestickSeries();

        const socket = io();
        let currentTimeframe = '1m';

        function loadChartData(timeframe) {
            fetch(`/get_data/${timeframe}`)
                .then(response => response.json())
                .then(data => {
                    candleSeries.setData(data);
                    currentTimeframe = timeframe;
                });
        }

        document.querySelectorAll('.timeframe-button').forEach(button => {
            button.addEventListener('click', () => {
                const timeframe = button.getAttribute('data-timeframe');
                loadChartData(timeframe);
            });
        });

        loadChartData(currentTimeframe);

        Object.keys({{ timeframes|tojson }}).forEach(tf => {
            socket.on(`update_chart_${tf}`, function(newBar) {
                if (tf === currentTimeframe) {
                    candleSeries.update(newBar);
                }
            });
        });
    </script>
</body>
</html>
"""
@app.route('/')
def index():
    return render_template_string(index_html, timeframes=list(timeframes.keys()))

@app.route('/get_data/<timeframe>')
def get_data(timeframe):
    if timeframe in chart_data:
        return jsonify(chart_data[timeframe].data[-250:])
    return jsonify([])

if __name__ == '__main__':
    load_data_from_csv()
    
    ws = websocket.WebSocketApp(ws_url,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close,
                                on_open=on_open)
    
    wst = threading.Thread(target=ws.run_forever)
    wst.daemon = True
    wst.start()

    save_data_thread = threading.Thread(target=save_data_to_csv)
    save_data_thread.daemon = True
    save_data_thread.start()
    
    socketio.run(app, debug=True, use_reloader=False)