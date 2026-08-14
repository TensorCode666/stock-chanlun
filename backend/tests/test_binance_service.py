"""加密货币数据服务：符号规范化与级别映射（不发起真实网络请求）。"""
import os
import sys
import unittest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from services.binance_service import LEVEL_TO_INTERVAL, normalize_symbol


class NormalizeSymbolTests(unittest.TestCase):
    def test_lowercase_and_dash(self):
        self.assertEqual(normalize_symbol("btc-usdt"), "BTCUSDT")

    def test_underscore_and_slash(self):
        self.assertEqual(normalize_symbol("eth_usdt"), "ETHUSDT")
        self.assertEqual(normalize_symbol("eth/usdt"), "ETHUSDT")

    def test_already_normalized(self):
        self.assertEqual(normalize_symbol("BTCUSDT"), "BTCUSDT")


class LevelToIntervalTests(unittest.TestCase):
    def test_all_frontend_levels_mapped(self):
        for level in ("1min", "5min", "15min", "30min", "60min", "4h", "daily", "weekly", "monthly"):
            self.assertIn(level, LEVEL_TO_INTERVAL)

    def test_4h_maps_to_binance_4h_interval(self):
        self.assertEqual(LEVEL_TO_INTERVAL["4h"], "4h")

    def test_minute_levels_are_true_minutes(self):
        # 与 A 股不同：加密货币 1min 直接对应 Binance 1m，无需降级为 5min
        self.assertEqual(LEVEL_TO_INTERVAL["1min"], "1m")

    def test_daily_weekly_monthly(self):
        self.assertEqual(LEVEL_TO_INTERVAL["daily"], "1d")
        self.assertEqual(LEVEL_TO_INTERVAL["weekly"], "1w")
        self.assertEqual(LEVEL_TO_INTERVAL["monthly"], "1M")


if __name__ == "__main__":
    unittest.main()
