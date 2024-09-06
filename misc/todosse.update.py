@app.route('/history')
def history():
    symbol = request.args.get('symbol')
    resolution = request.args.get('resolution')
    from_time = int(request.args.get('from'))
    to_time = int(request.args.get('to'))
    
    # Example: Call the simulateCandleData function to get data
    bars = simulateCandleData(symbol, from_time, to_time)
    
    # Return data in the required format
    return jsonify({
        "s": "ok",
        "t": [bar["time"] for bar in bars],
        "o": [bar["open"] for bar in bars],
        "h": [bar["high"] for bar in bars],
        "l": [bar["low"] for bar in bars],
        "c": [bar["close"] for bar in bars],
        "v": [bar["volume"] for bar in bars]
    })

@app.route('/config')
def config():
    return jsonify({
        "supported_resolutions": ['1', '5', '15', '30', '60', 'D', 'W', 'M'],
        "supports_search": True,
        "supports_group_request": False,
        "supports_marks": False,
        "supports_timescale_marks": False,
        "supports_time": True,
        "exchanges": [
            {"value": "NYSE", "name": "NYSE", "desc": "NYSE"},
        ],
        "symbols_types": [
            {"name": "Stock", "value": "stock"},
        ]
    })


            # {**symbol, "supported_resolutions": ['1', '5', '15', '30', '60', 'D', 'W', 'M']}


@app.route('/realtime/<symbol>')
def realtime(symbol):
    def generate():
        while True:
            time.sleep(1)  # Simulate delay in receiving new data
            # Generate a random OHLCV update
            new_bar = {
                "time": int(datetime.now().timestamp()),
                "open": np.random.normal(100, 5),
                "high": np.random.normal(105, 5),
                "low": np.random.normal(95, 5),
                "close": np.random.normal(100, 5),
                "volume": int(np.random.normal(10000, 500))
            }
            yield f"data: {new_bar}\n\n"
    
    return Response(generate(), content_type='text/event-stream')

if __name__ == '__main__':
    app.run(port=3001, debug=True)
