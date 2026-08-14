"""加密货币缠论分析：K 线拉取失败/不足时的处理，及正常路径下引擎复用。"""
import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import pandas as pd
from fastapi import HTTPException

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.crypto_analysis import crypto_cache_key, run_crypto_analysis, serialize_crypto_analysis


def _sample_df(n: int = 30) -> pd.DataFrame:
    base = datetime(2024, 1, 1)
    rows = []
    price = 100.0
    for i in range(n):
        price += (1 if i % 2 == 0 else -0.5)
        rows.append({
            "date": base + timedelta(hours=i),
            "open": price,
            "high": price + 1,
            "low": price - 1,
            "close": price + 0.3,
            "volume": 10.0 + i,
        })
    return pd.DataFrame(rows)


class CryptoCacheKeyTests(unittest.TestCase):
    def test_key_includes_symbol_level_limit(self):
        key = crypto_cache_key("BTCUSDT", "daily", 500)
        self.assertEqual(key, "BTCUSDT:daily:500")


class RunCryptoAnalysisTests(unittest.TestCase):
    def test_insufficient_klines_raises_404(self):
        with patch("core.crypto_analysis.get_kline_hist", return_value=pd.DataFrame()):
            with self.assertRaises(HTTPException) as ctx:
                run_crypto_analysis("BTCUSDT", "daily")
            self.assertEqual(ctx.exception.status_code, 404)

    def test_valid_klines_produce_analysis_with_symbol(self):
        with patch("core.crypto_analysis.get_kline_hist", return_value=_sample_df(30)):
            result = run_crypto_analysis("ethusdt", "60min", kline_limit=100)
        self.assertEqual(result.stock_code, "ethusdt")
        self.assertEqual(result.level, "60min")
        self.assertGreater(len(result.klines), 0)

    def test_serialize_uses_symbol_key_not_stock_code(self):
        with patch("core.crypto_analysis.get_kline_hist", return_value=_sample_df(30)):
            result = run_crypto_analysis("BTCUSDT", "daily", kline_limit=100)
        payload = serialize_crypto_analysis(result)
        self.assertEqual(payload["symbol"], "BTCUSDT")
        self.assertNotIn("data_period", payload)  # A 股分钟降级备注不适用于加密货币


if __name__ == "__main__":
    unittest.main()
