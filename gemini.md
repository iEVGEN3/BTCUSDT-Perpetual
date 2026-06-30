# Схемы данных и операционные правила

## Правило одновременного запуска (Anti-Concurrency)
- **Запрет**: Запрещено параллельное выполнение бота локально и в облаке. 
- **Контроль**: Перед деплоем на сервер Hugging Face все локальные процессы `python features/bot.py` должны быть завершены принудительно. Перед тестированием локально серверный инстанс должен быть остановлен или отключен от поллинга.

---

## Схемы баз данных PostgreSQL (Neon.tech)

### Таблица подписок (`subscriptions`)
| Поле | Тип | Ограничение | Описание |
|---|---|---|---|
| `chat_id` | BIGINT | PRIMARY KEY | Telegram ID пользователя или чата |
| `username` | VARCHAR(100) | NULLABLE | Telegram username подписчика |
| `subscribed_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Время подписки |
| `arbitrage_subscribed` | BOOLEAN | DEFAULT FALSE | Флаг подписки на арбитраж |

### Таблица истории сигналов (`signal_history`)
| Поле | Тип | Ограничение | Описание |
|---|---|---|---|
| `id` | SERIAL | PRIMARY KEY | Автоинкрементный ID |
| `ticker` | VARCHAR(20) | NOT NULL | Тикер актива |
| `price` | NUMERIC | NOT NULL | Цена входа |
| `signal_type` | VARCHAR(20) | NOT NULL | Тип сигнала: `BUY`, `SELL`, или `WAIT` |
| `timestamp` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Время генерации |

---

## Форматы сообщений Telegram-бота (Украинский язык)

### Стандартный торговый сигнал (Rich HTML)
```html
<h2>📈 Актив: <TICKER></h2>
<p>Поточна консенсус-ціна: <b>$<PRICE></b></p>
<h3>Рекомендація: <mark><SIGNAL_TYPE></mark></h3>
<hr/>
<h4>Що робити по кроках:</h4>
<ol>
  <li><STEP_1></li>
  <li><STEP_2></li>
  <li><STEP_3></li>
</ol>
<hr/>
<h4>Рівні угоди та ризик-менеджмент:</h4>
<table bordered striped>
  <tr><th>Параметр</th><th>Значення</th></tr>
  <tr><td>🛡️ <b>Стоп-лосс</b> (обмеження ризику)</td><td>$<STOP_LOSS></td></tr>
  <tr><td>🎯 <b>Ціль 1</b> (фіксація 50%)</td><td>$<TARGET_1></td></tr>
  <tr><td>🎯 <b>Ціль 2</b> (фіксація 50%)</td><td>$<TARGET_2></td></tr>
</table>
<br/>
<blockquote>
  <b>Обґрунтування:</b> <METAPHOR_EXPLANATION>
</blockquote>
<hr/>
<details open>
  <summary>📊 Параметри ризику</summary>
  <ul>
    <li>Рекомендований ризик на угоду: <b>0.5–1% від депозиту</b></li>
    <li>Впевненість моделі: <b><CONFIDENCE_PCT>%</b></li>
    <li>Резюме: <i><ONE_LINER></i></li>
  </ul>
</details>

[If WAIT, optional Alternatives block]
<hr/>
<details open>
  <summary>💡 Доступна альтернатива</summary>
  <p>Рекомендується розглянути: <b><ALT_TICKER></b> (статус: <mark><ALT_SIGNAL></mark>)</p>
  <ul>
    <li>Вхід: $<ALT_PRICE></li>
    <li>Стоп-лосс: $<ALT_SL></li>
    <li>Ціль 1: $<ALT_TP></li>
  </ul>
  <blockquote><ALT_METAPHOR></blockquote>
</details>
```

### Арбитражная связка (Rich HTML)
```html
<h2>🚨 АРБІТРАЖНА ЗВ'ЯЗКА ДЕТЕКТОВАНА 🚨</h2>
<p>Актив: <b><TICKER></b></p>
<p>Різниця в ціні (спред): <b><SPREAD_PCT>%</b></p>
<hr/>
<p>📈 Купівля на Binance: <b>$<BINANCE_PRICE></b></p>
<p>📉 Продаж на Bybit: <b>$<BYBIT_PRICE></b></p>
<hr/>
<h4>Що робити по кроках:</h4>
<ol>
  <li>Купити актив на спотовому/фьючерсному ринку Binance за $<BINANCE_PRICE>.</li>
  <li>Переказати / хеджувати позицію на Bybit за ціною $<BYBIT_PRICE>.</li>
  <li>Закрити угоду при схлопуванні спреду.</li>
</ol>
<blockquote>Рекомендований ризик: Мінімальний (без плеча)</blockquote>
<footer>Моніторинг активний 24/7.</footer>
```
