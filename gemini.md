# Data Schemas & Operational Rules

## PostgreSQL Database Schemas (Neon.tech)

### Subscriptions Table (`subscriptions`)
| Field | Type | Constraint | Description |
|---|---|---|---|
| `chat_id` | BIGINT | PRIMARY KEY | Telegram user or chat identifier |
| `username` | VARCHAR(100) | NULLABLE | Telegram username of the subscriber |
| `subscribed_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Date and time when the user subscribed to trading signals |
| `arbitrage_subscribed` | BOOLEAN | DEFAULT FALSE | Opt-in flag for arbitrage spread alerts |

### Signal History Table (`signal_history`)
| Field | Type | Constraint | Description |
|---|---|---|---|
| `id` | SERIAL | PRIMARY KEY | Unique auto-incrementing ID |
| `ticker` | VARCHAR(20) | NOT NULL | Cryptocurrency symbol (e.g., BTC, ETH) |
| `price` | NUMERIC | NOT NULL | Entry price when the signal was generated |
| `signal_type` | VARCHAR(20) | NOT NULL | Signal type: `BUY`, `SELL`, or `WAIT` |
| `timestamp` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Time of signal generation |

### Arbitrage History Table (`arbitrage_history`)
| Field | Type | Constraint | Description |
|---|---|---|---|
| `id` | SERIAL | PRIMARY KEY | Unique auto-incrementing ID |
| `ticker` | VARCHAR(20) | NOT NULL | Cryptocurrency symbol (e.g., BTC, ETH) |
| `binance_price` | NUMERIC | NOT NULL | Price on Binance Futures |
| `bybit_price` | NUMERIC | NOT NULL | Price on Bybit Futures |
| `spread_pct` | NUMERIC | NOT NULL | Calculated percentage difference: `((bybit_price - binance_price) / binance_price) * 100` |
| `timestamp` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Time when the opportunity was detected |

---

## Market Data Analysis Schema (Consensus of Binance, Bybit & TradingView)
```json
{
  "success": true,
  "ticker": "BTCUSDT",
  "prices": {
    "binance": 61250.0,
    "bybit": 61255.5,
    "consensus": 61252.75
  },
  "rsi": 52.4,
  "macd": {
    "macd_curr": 12.5,
    "signal_curr": 8.2,
    "macd_prev": 11.1,
    "signal_prev": 7.1
  },
  "ema50": 60900.0,
  "tradingview_recommendation": "BUY"
}
```

---

## Telegram Bot Signal Output Format

### Standard Trading Signal
```text
Актив: <TICKER>
Цена сейчас: ≈ $<PRICE>
What to do right now: <SIGNAL_TYPE_EMOJI> <SIGNAL_TYPE>
Что делать по шагам:
1. <STEP_1>
2. <STEP_2>
3. <STEP_3>
Конкретные уровни:
• Стоп-лосс: $<STOP_LOSS>
• Цель 1: $<TARGET_1>
• Цель 2: $<TARGET_2>
Почему так: <METAPHOR_EXPLANATION>
Риск: Только 0.5–1% от депозита.
Уверенность: <CONFIDENCE_PCT>%
Одной строкой: <ONE_LINER>

[If WAIT, optional Alternatives block]
Альтернативы сейчас:
• <ALT_TICKER> — <ALT_SIGNAL> | <ALT_METAPHOR> | Вход: $<ALT_PRICE>, Стоп: $<ALT_SL>, Цель: $<ALT_TP>
```

### Arbitrage Spread Alert
```text
🚨 АРБИТРАЖНАЯ СВЯЗКА ДЕТЕКТИРОВАНА 🚨
Актив: <TICKER>
Разница в цене (спред): <SPREAD_PCT>%

📈 Покупка на Binance: $<BINANCE_PRICE>
📉 Продажа на Bybit: $<BYBIT_PRICE>

Действие по шагам:
1. Купить актив на спотовом/фьючерсном рынке Binance за $<BINANCE_PRICE>.
2. Перевести / хеджировать позицию на Bybit по цене $<BYBIT_PRICE>.
3. Закрыть сделку при схлопывании спреда.
Рекомендуемый риск: Минимальный (без плеча).
Мониторинг активен 24/7.
```
