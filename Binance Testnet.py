import pandas as pd
import numpy as np
from datetime import datetime, timedelta, UTC
from binance.client import Client

API_KEY = "Add Binance futures testnet api key here"
API_SECRET = "Add Binance futures testnet Secret key here"
LIQUIDITY_WALL_THRESHOLD = 0.3
HISTORICAL_DAYS = 365

COINS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "SOLUSDT", "DOTUSDT"
]

client = Client(API_KEY, API_SECRET, testnet=True)


def get_valid_futures_symbols():
    exchange_info = client.futures_exchange_info()
    symbols = [s['symbol'] for s in exchange_info['symbols']]
    return set(symbols)


VALID_FUTURES = get_valid_futures_symbols()
COINS = [c for c in COINS if c in VALID_FUTURES]

print(f"Valid Futures Symbols Loaded: {len(COINS)}")
print(COINS)


def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def rsi(series, period=14):
    delta = series.diff()
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = pd.Series(gain).rolling(period).mean()
    avg_loss = pd.Series(loss).rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def atr(df, period=14):
    high_low = df['high'] - df['low']
    high_close = abs(df['high'] - df['close'].shift())
    low_close = abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def check_liquidity_wall(df):
    avg_vol = df['volume'].rolling(20).mean()
    last_vol = df['volume'].iloc[-1]
    return last_vol > avg_vol.iloc[-1] * (1 + LIQUIDITY_WALL_THRESHOLD)


def calc_tp_sl(price, df, side):
    highs = df['high']
    lows = df['low']
    resistance = highs.rolling(20).max().iloc[-1]
    support = lows.rolling(20).min().iloc[-1]
    if side == "LONG":
        return resistance, support
    else:
        return support, resistance


def generate_signals(df_exec, df_filter):

    signals = []
    df_exec['ema20'] = ema(df_exec['close'], 20)
    df_exec['ema200'] = ema(df_exec['close'], 200)
    df_exec['rsi'] = rsi(df_exec['close'], 14)
    df_filter['ema200'] = ema(df_filter['close'], 200)

    ratio = len(df_exec) // len(df_filter)

    for i in range(200, len(df_exec)):
        last_exec = df_exec.iloc[i]
        filter_idx = min(i // ratio, len(df_filter) - 1)
        last_filter = df_filter.iloc[filter_idx]

        wall_ok = check_liquidity_wall(df_exec.iloc[i - 20:i])

        if last_exec['close'] > last_exec['ema200'] and last_filter['close'] > last_filter['ema200']:
            if abs(last_exec['close'] - last_exec['ema20']) / last_exec['ema20'] < 0.002 and last_exec[
                'rsi'] < 60 and wall_ok:
                signals.append(("LONG", i))
        elif last_exec['close'] < last_exec['ema200'] and last_filter['close'] < last_filter['ema200']:
            if abs(last_exec['close'] - last_exec['ema20']) / last_exec['ema20'] < 0.002 and last_exec[
                'rsi'] > 40 and wall_ok:
                signals.append(("SHORT", i))
    return signals


def backtest(symbol, exec_interval, filter_interval, exec_name, filter_name):
    end_time = datetime.now(UTC)
    start_time = end_time - timedelta(days=HISTORICAL_DAYS)

    klines_exec = client.futures_klines(
        symbol=symbol,
        interval=exec_interval,
        start_str=start_time.strftime("%d %b %Y %H:%M:%S"),
        end_str=end_time.strftime("%d %b %Y %H:%M:%S")
    )
    klines_filter = client.futures_klines(
        symbol=symbol,
        interval=filter_interval,
        start_str=start_time.strftime("%d %b %Y %H:%M:%S"),
        end_str=end_time.strftime("%d %b %Y %H:%M:%S")
    )

    df_exec = pd.DataFrame(klines_exec,
                           columns=['time', 'open', 'high', 'low', 'close', 'volume', 'x', 'y', 'z', 'a', 'b', 'c'])
    df_filter = pd.DataFrame(klines_filter,
                             columns=['time', 'open', 'high', 'low', 'close', 'volume', 'x', 'y', 'z', 'a', 'b', 'c'])

    df_exec[['open', 'high', 'low', 'close', 'volume']] = df_exec[['open', 'high', 'low', 'close', 'volume']].astype(
        float)
    df_filter[['open', 'high', 'low', 'close', 'volume']] = df_filter[
        ['open', 'high', 'low', 'close', 'volume']].astype(float)

    df_exec['time'] = pd.to_datetime(df_exec['time'], unit='ms')
    df_filter['time'] = pd.to_datetime(df_filter['time'], unit='ms')

    signals = generate_signals(df_exec, df_filter)

    trades = []
    tp_hits = 0
    sl_hits = 0

    for side, idx in signals:
        entry_price = df_exec['close'].iloc[idx]
        entry_time = df_exec['time'].iloc[idx]
        tp, sl = calc_tp_sl(entry_price, df_exec.iloc[max(0, idx - 20):idx], side)

        future = df_exec.iloc[idx + 1:]
        exit_price = None
        exit_time = None
        outcome = "OPEN"

        for j in range(len(future)):
            if side == "LONG":
                if future['high'].iloc[j] >= tp:
                    exit_price = tp
                    exit_time = future['time'].iloc[j]
                    outcome = "TP"
                    tp_hits += 1
                    break
                elif future['low'].iloc[j] <= sl:
                    exit_price = sl
                    exit_time = future['time'].iloc[j]
                    outcome = "SL"
                    sl_hits += 1
                    break
            else:
                if future['low'].iloc[j] <= tp:
                    exit_price = tp
                    exit_time = future['time'].iloc[j]
                    outcome = "TP"
                    tp_hits += 1
                    break
                elif future['high'].iloc[j] >= sl:
                    exit_price = sl
                    exit_time = future['time'].iloc[j]
                    outcome = "SL"
                    sl_hits += 1
                    break

        if exit_price:
            if side == "LONG":
                pnl_pct = ((exit_price - entry_price) / entry_price) * 100
            else:
                pnl_pct = ((entry_price - exit_price) / entry_price) * 100
        else:
            pnl_pct = 0
            exit_price = df_exec['close'].iloc[-1]
            exit_time = df_exec['time'].iloc[-1]

        trades.append({
            'symbol': symbol,
            'timeframe': exec_name,
            'filter_tf': filter_name,
            'side': side,
            'entry_time': entry_time,
            'entry_price': entry_price,
            'tp': tp,
            'sl': sl,
            'exit_time': exit_time,
            'exit_price': exit_price,
            'outcome': outcome,
            'pnl_pct': pnl_pct
        })

    return {
        'symbol': symbol,
        'timeframe': exec_name,
        'filter_tf': filter_name,
        'signals': len(signals),
        'TP_hit': tp_hits,
        'SL_hit': sl_hits,
        'accuracy_%': (tp_hits / len(signals) * 100) if len(signals) > 0 else 0
    }, trades


def main_backtest():
    all_trades = []
    summary_results = []

    configs = [
        (Client.KLINE_INTERVAL_1HOUR, Client.KLINE_INTERVAL_4HOUR, "1H", "4H"),
        (Client.KLINE_INTERVAL_4HOUR, Client.KLINE_INTERVAL_1DAY, "4H", "1D")
    ]

    for exec_interval, filter_interval, exec_name, filter_name in configs:
        print(f"\n{'=' * 60}")
        print(f"Testing {exec_name} execution with {filter_name} filter")
        print(f"{'=' * 60}")

        for symbol in COINS:
            print(f"Backtesting {symbol} on {exec_name}/{filter_name}...")
            try:
                result, trades = backtest(symbol, exec_interval, filter_interval, exec_name, filter_name)
                summary_results.append(result)
                all_trades.extend(trades)
            except Exception as e:
                print(f"Skipping {symbol} due to error: {e}")

    df_summary = pd.DataFrame(summary_results)
    print("\n" + "=" * 60)
    print("SUMMARY RESULTS")
    print("=" * 60)
    print(df_summary.to_string(index=False))

    df_trades = pd.DataFrame(all_trades)

    df_summary.to_csv("backtest_summary.csv", index=False)
    df_trades.to_csv("backtest_all_trades.csv", index=False)

    print("\n" + "=" * 60)
    print("FILES SAVED:")
    print("=" * 60)
    print("✓ backtest_summary.csv - Overall results per symbol/timeframe")
    print("✓ backtest_all_trades.csv - Detailed trade-by-trade breakdown")
    print(f"\nTotal Trades Executed: {len(df_trades)}")

    if len(df_trades) > 0:
        print("\n" + "=" * 60)
        print("OVERALL STATISTICS")
        print("=" * 60)
        winning_trades = df_trades[df_trades['outcome'] == 'TP']
        losing_trades = df_trades[df_trades['outcome'] == 'SL']

        print(f"Total Trades: {len(df_trades)}")
        print(f"Winning Trades: {len(winning_trades)} ({len(winning_trades) / len(df_trades) * 100:.2f}%)")
        print(f"Losing Trades: {len(losing_trades)} ({len(losing_trades) / len(df_trades) * 100:.2f}%)")
        print(f"Average Win: {winning_trades['pnl_pct'].mean():.2f}%")
        print(f"Average Loss: {losing_trades['pnl_pct'].mean():.2f}%")
        print(f"Total PnL: {df_trades['pnl_pct'].sum():.2f}%")

        print("\n" + "=" * 60)
        print("BY TIMEFRAME")
        print("=" * 60)
        for tf in df_trades['timeframe'].unique():
            tf_trades = df_trades[df_trades['timeframe'] == tf]
            tf_wins = tf_trades[tf_trades['outcome'] == 'TP']
            print(f"\n{tf} Timeframe:")
            print(f"  Total Trades: {len(tf_trades)}")
            print(f"  Win Rate: {len(tf_wins) / len(tf_trades) * 100:.2f}%")
            print(f"  Total PnL: {tf_trades['pnl_pct'].sum():.2f}%")


if __name__ == "__main__":
    main_backtest()