# Binance Futures Testnet Backtester

This is a small **side project** script for experimenting with a simple signal + backtesting idea on **Binance USDT-M Futures testnet** market data.

## Not financial advice

**This project is for educational/testing purposes only and is NOT financial advice.**  
Nothing here is a recommendation to buy/sell/hold any asset. Use at your own risk.

## What it does

- Fetches historical futures klines from Binance (testnet) for a list of symbols (filters to valid futures symbols).
- Builds signals using:
  - EMA(20) and EMA(200)
  - RSI(14)
  - A basic “liquidity wall” check using volume vs 20-period average volume
- Runs a simple TP/SL evaluation using recent rolling support/resistance.
- Exports results to CSV:
  - `backtest_summary.csv` — per symbol/timeframe summary
  - `backtest_all_trades.csv` — detailed trade-by-trade output

## Requirements

- Python 3.10+ recommended
- Packages:
  - `python-binance`
  - `pandas`
  - `numpy`

Install:

```bash
pip install python-binance pandas numpy
```

## Setup

1. Open `Binance Testnet.py`
2. Set your Binance **Futures testnet** API credentials:

```python
API_KEY = "Add Binance futures testnet api key here"
API_SECRET = "Add Binance futures testnet Secret key here"
```

Notes:
- The script uses `Client(API_KEY, API_SECRET, testnet=True)`.
- Keep keys private. Don’t commit them to git or share them.

## Run

```bash
python "Binance Testnet.py"
```

The script prints progress and summary tables in the console, then writes the CSV outputs into the same folder.

## Configuration (in the script)

- `COINS`: symbols to test (the script also filters to valid futures symbols)
- `HISTORICAL_DAYS`: how many days of data to request
- `LIQUIDITY_WALL_THRESHOLD`: volume spike threshold used by the liquidity wall check
- Timeframe configs are defined in `configs` inside `main_backtest()`:
  - 1H execution with 4H filter
  - 4H execution with 1D filter

## Outputs

- `backtest_summary.csv`: counts of signals, TP hits, SL hits, accuracy %
- `backtest_all_trades.csv`: entry/exit times, TP/SL levels, outcome, and PnL %

## Disclaimer

This code is experimental and simplified:
- Backtests can be misleading (fees, slippage, funding, latency, partial fills, execution constraints, survivorship bias, and parameter overfitting are not fully modeled).
- Past performance does not predict future results.

Again: **this is a side project and NOT financial advice.**
