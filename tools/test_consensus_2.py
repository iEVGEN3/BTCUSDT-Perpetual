import sys
import os

# Add features directory to sys.path
curr_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(curr_dir)
features_dir = os.path.join(parent_dir, 'features')
sys.path.append(features_dir)

# Import functions to test
from signals import generate_signal
from market_data import analyze_market

def test_ticker(ticker):
    print("=" * 60)
    print(f"Testing consensus 2.0 for {ticker.upper()}...")
    print("=" * 60)
    
    # 1. Analyze market (raw values)
    raw_data = analyze_market(ticker)
    if raw_data['success']:
        print(f"Price: {raw_data['price']}")
        print(f"RSI: {raw_data['rsi']:.2f}")
        print(f"MACD Current: {raw_data['macd']['macd_curr']:.4f}, Signal: {raw_data['macd']['signal_curr']:.4f}")
        print(f"EMA50: {raw_data['ema50']:.2f}")
        atr_pct = (raw_data['atr'] / raw_data['price']) * 100 if raw_data['price'] > 0 else 0
        print(f"ATR (14): {raw_data['atr']:.4f} ({atr_pct:.2f}%)")
        print(f"ADX (14): {raw_data['adx']:.2f}")
        print(f"TradingView Recommendation: {raw_data['tradingview_recommendation']}")
    else:
        print(f"Market analysis error: {raw_data.get('error')}")
        return
        
    # 2. Generate signal
    sig = generate_signal(ticker)
    if sig['success']:
        print(f"Signal: {sig['signal']}")
        print(f"Confidence: {sig['confidence']}%")
        print(f"Stop Loss: ${sig['stop_loss']}")
        print(f"Target 1: ${sig['target1']}")
        print(f"Target 2: ${sig['target2']}")
        print(f"Metaphor (Ukrainian): {sig['metaphor']}")
        print(f"One-liner: {sig['one_liner']}")
        print("Steps:")
        for idx, step in enumerate(sig['steps'], 1):
            print(f"  {idx}. {step}")
    else:
        print(f"Signal generation error: {sig.get('error')}")

if __name__ == "__main__":
    tickers_to_test = ['btc', 'eth', 'sol']
    for t in tickers_to_test:
        test_ticker(t)
