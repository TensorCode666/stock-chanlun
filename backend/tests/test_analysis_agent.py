import os
import sys
import unittest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from ai.analysis_agent import (  # noqa: E402
    _format_divergence_for_prompt,
    build_analysis_prompt,
    parse_llm_response,
)


class FormatDivergencePromptTests(unittest.TestCase):
    def test_format_includes_force_and_oscillators(self):
        div = {
            "type": "bottom",
            "probability": 0.82,
            "macd_ratio": 0.72,
            "macd_force": "directional",
            "rsi_confirm": True,
            "kdj_confirm": False,
            "description": "价格新低0.5但力度减弱至72%",
            "price_drop": 0.012,
        }
        text = _format_divergence_for_prompt(div)
        self.assertIn("同向柱累计", text)
        self.assertIn("MACD力度比:0.72", text)
        self.assertIn("RSI是", text)
        self.assertIn("KDJ否", text)
        self.assertIn("价格下探幅度", text)

    def test_build_analysis_prompt_embeds_formatted_divergence(self):
        div = {
            "type": "top",
            "probability": 0.71,
            "macd_ratio": 0.8,
            "macd_force": "abs",
            "rsi_confirm": False,
            "kdj_confirm": False,
            "description": "测试",
            "price_rise": 0.02,
        }
        prompt = build_analysis_prompt(
            code="000001",
            level="daily",
            klines=[
                {
                    "date": "2024-01-01",
                    "open": 1,
                    "high": 2,
                    "low": 0.5,
                    "close": 1.5,
                    "volume": 100,
                }
            ],
            trend="上涨",
            divergence=div,
            signals=[],
            zhongshus=[],
            bis=[],
        )
        self.assertIn("绝对值面积", prompt)
        self.assertIn("背驰信号", prompt)


class ParseLlmResponseTests(unittest.TestCase):
    def test_dict_response_passthrough(self):
        out = parse_llm_response('{"direction":"买入","confidence":0.8}')
        self.assertEqual(out["direction"], "买入")
        self.assertEqual(out["confidence"], 0.8)

    def test_json_array_returns_none(self):
        out = parse_llm_response("[]")
        self.assertIsNone(out)

    def test_invalid_json_returns_none(self):
        out = parse_llm_response("not json at all")
        self.assertIsNone(out)


if __name__ == "__main__":
    unittest.main()
