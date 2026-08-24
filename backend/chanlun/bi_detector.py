"""
笔检测器 — 基于分型识别笔
"""
import numpy as np
import pandas as pd
from typing import Optional
from datetime import datetime
from .elements import Bi
from .fenxing_detector import FenxingDetector, Fenxing


class BiDetector:
    """
    笔规则:
    1. 顶分型 + 底分型 = 一笔（向上笔: 底→顶，向下笔: 顶→底）
    2. 笔至少需要5根K线（含分型）
    3. 同级别笔由连续顶底分型构成
    """

    def __init__(self, klines: pd.DataFrame):
        self.klines = klines.reset_index(drop=True)
        self._date_values = self.klines["date"].values
        self._fenxing_detector = FenxingDetector(klines)
        self._fenxings: list[Fenxing] = []

    @property
    def processed_klines(self) -> pd.DataFrame:
        """包含关系处理后的 K 线（与笔/分型检测一致）。"""
        return self._fenxing_detector.klines

    @staticmethod
    def compress_fenxings(fenxings: list[Fenxing]) -> list[Fenxing]:
        """
        压缩分型序列：连续同类型分型仅保留更“极值”的那个。
        - 连续 top：保留 high 更高者
        - 连续 bottom：保留 low 更低者
        """
        if not fenxings:
            return []

        out: list[Fenxing] = [fenxings[0]]
        for fx in fenxings[1:]:
            last = out[-1]
            if fx.type != last.type:
                out.append(fx)
                continue

            if fx.type == "top":
                if fx.high >= last.high:
                    out[-1] = fx
            else:  # bottom
                if fx.low <= last.low:
                    out[-1] = fx

        return out

    def detect(self, min_bars: int = 5) -> list[Bi]:
        """
        检测所有笔
        min_bars: 笔最少K线数（默认5根）
        """
        self._fenxings = self.compress_fenxings(self._fenxing_detector.detect())
        if len(self._fenxings) < 2:
            return []

        bis: list[Bi] = []
        i = 0

        while i < len(self._fenxings) - 1:
            fx1 = self._fenxings[i]
            fx2 = self._fenxings[i + 1]

            if fx1.type == "bottom" and fx2.type == "top":
                bar_count = self._count_klines_between(fx1.date, fx2.date)
                if bar_count >= min_bars:
                    bis.append(Bi(
                        id=f"bi_up_{len(bis)+1}",
                        start=fx1.date,
                        end=fx2.date,
                        direction="up",
                        high=float(fx2.high),
                        low=float(fx1.low),
                        start_price=float(fx1.low),
                        end_price=float(fx2.high),
                    ))
                i += 1

            elif fx1.type == "top" and fx2.type == "bottom":
                bar_count = self._count_klines_between(fx1.date, fx2.date)
                if bar_count >= min_bars:
                    bis.append(Bi(
                        id=f"bi_down_{len(bis)+1}",
                        start=fx1.date,
                        end=fx2.date,
                        direction="down",
                        high=float(fx1.high),
                        low=float(fx2.low),
                        start_price=float(fx1.high),
                        end_price=float(fx2.low),
                    ))
                i += 1
            else:
                i += 1

        return bis

    def _count_klines_between(self, start: datetime, end: datetime) -> int:
        """计算两个时间之间的K线数量（searchsorted，避免全表布尔掩码）"""
        dates = self._date_values
        # np.datetime64 显式转换：部分 numpy/pandas 版本组合下，datetime64 数组与裸
        # datetime/Timestamp 标量比较会抛 TypeError，需先转换为同类型再比较
        left = int(np.searchsorted(dates, np.datetime64(start), side="left"))
        right = int(np.searchsorted(dates, np.datetime64(end), side="right"))
        return max(0, right - left)
