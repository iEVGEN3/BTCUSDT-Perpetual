import unittest
import math
from market_data import get_live_price, analyze_market
from signals import generate_signal

class TestTradingTrainerBot(unittest.TestCase):
    
    def test_live_price_fetching(self):
        """Проверяет получение цены с Binance для основных монет."""
        for ticker in ['BTC', 'ETH', 'SOL']:
            try:
                price = get_live_price(ticker)
                print(f"Тест цены: {ticker} = ${price}")
                self.assertIsInstance(price, float)
                self.assertGreater(price, 0)
            except Exception as e:
                self.fail(f"Не удалось получить цену для {ticker}: {e}")

    def test_market_analysis(self):
        """Проверяет вычисление индикаторов (RSI, MACD, EMA)."""
        res = analyze_market('BTC')
        self.assertTrue(res['success'])
        self.assertIn('price', res)
        self.assertIn('rsi', res)
        self.assertIn('macd', res)
        self.assertIn('ema50', res)
        self.assertIsInstance(res['rsi'], float)
        self.assertGreaterEqual(res['rsi'], 0)
        self.assertLessEqual(res['rsi'], 100)

    def test_signal_structure_and_math(self):
        """Проверяет корректность структуры сигнала и математику расчета целей/стопов."""
        res = generate_signal('BTC')
        self.assertTrue(res['success'])
        self.assertIn('ticker', res)
        self.assertEqual(res['ticker'], 'BTC')
        self.assertIn('price', res)
        self.assertIn('signal', res)
        self.assertIn('steps', res)
        self.assertIn('stop_loss', res)
        self.assertIn('target1', res)
        self.assertIn('target2', res)
        self.assertIn('metaphor', res)
        self.assertIn('confidence', res)
        self.assertIn('one_liner', res)
        
        # Проверяем математику расчетов (на основе сохраненных raw-значений)
        raw_price = res['raw_price']
        sl = res['stop_loss']
        t1 = res['target1']
        t2 = res['target2']
        sig = res['signal']
        
        # Для BTC цены больше $1, поэтому округляются до целых
        if sig == "✅ КУПУЙ":
            expected_sl = int(round(raw_price * 0.985))
            expected_t1 = int(round(raw_price * 1.03))
            expected_t2 = int(round(raw_price * 1.06))
            self.assertEqual(sl, expected_sl, "Стоп-лосс на покупку должен быть ровно 1.5% вниз")
            self.assertEqual(t1, expected_t1, "Цель 1 на покупку должна быть ровно 3% вверх")
            self.assertEqual(t2, expected_t2, "Цель 2 на покупку должна быть ровно 6% вверх")
        elif sig == "❌ ПРОДАВАЙ":
            expected_sl = int(round(raw_price * 1.015))
            expected_t1 = int(round(raw_price * 0.97))
            expected_t2 = int(round(raw_price * 0.94))
            self.assertEqual(sl, expected_sl, "Стоп-лосс на продажу должен быть ровно 1.5% вверх")
            self.assertEqual(t1, expected_t1, "Цель 1 на продажу должна быть ровно 3% вниз")
            self.assertEqual(t2, expected_t2, "Цель 2 на продажу должна быть ровно 6% вниз")
        else: # ЖДИ
            expected_sl = int(round(raw_price * 0.985))
            expected_t1 = int(round(raw_price * 1.03))
            expected_t2 = int(round(raw_price * 1.06))
            self.assertEqual(sl, expected_sl)
            self.assertEqual(t1, expected_t1)
            self.assertEqual(t2, expected_t2)

if __name__ == '__main__':
    unittest.main()
