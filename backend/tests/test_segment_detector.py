import os
import sys
import unittest
from datetime import datetime, timedelta

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from chanlun.elements import Bi, XiangSegment
from chanlun.segment_detector import SegmentDetector


class SegmentDetectorTests(unittest.TestCase):
    def setUp(self):
        self.t0 = datetime(2026, 1, 2, 9, 30)

    def _bi(self, idx: int, direction: str, start_min: int, end_min: int, high: float, low: float) -> Bi:
        start = self.t0 + timedelta(minutes=start_min)
        end = self.t0 + timedelta(minutes=end_min)
        return Bi(
            id=f"bi_{idx}",
            start=start,
            end=end,
            direction=direction,
            high=high,
            low=low,
            start_price=low if direction == "up" else high,
            end_price=high if direction == "up" else low,
        )

    def _segment(self, idx: int, direction: str, start_min: int, end_min: int, high: float, low: float) -> XiangSegment:
        start = self.t0 + timedelta(minutes=start_min)
        end = self.t0 + timedelta(minutes=end_min)
        return XiangSegment(
            id=f"xiang_{idx}",
            start=start,
            end=end,
            direction=direction,
            high=high,
            low=low,
            bi_ids=[f"bi_{idx}a", f"bi_{idx}b", f"bi_{idx}c"],
            level=2,
        )

    def test_detect_segments_returns_empty_when_bis_less_than_three(self):
        detector = SegmentDetector(
            bis=[self._bi(1, "up", 0, 5, 11.0, 9.0), self._bi(2, "up", 6, 10, 12.0, 10.0)]
        )
        self.assertEqual(detector.detect_segments(), [])

    def test_detect_segments_builds_segment_from_overlapping_same_direction_bis(self):
        bis = [
            self._bi(1, "up", 0, 5, 11.0, 9.2),
            self._bi(2, "up", 6, 10, 11.8, 9.5),
            self._bi(3, "up", 11, 15, 12.3, 9.8),
            # 第4笔同向且重叠，应该延伸进同一个线段
            self._bi(4, "up", 16, 20, 12.8, 10.0),
            # 反向笔，不参与上面线段延伸
            self._bi(5, "down", 21, 25, 12.5, 9.4),
        ]
        detector = SegmentDetector(bis=bis)

        segments = detector.detect_segments()
        self.assertEqual(len(segments), 1)
        seg = segments[0]
        self.assertEqual(seg.direction, "up")
        self.assertEqual(seg.bi_ids, ["bi_1", "bi_2", "bi_3", "bi_4"])
        self.assertEqual(seg.start, bis[0].start)
        self.assertEqual(seg.end, bis[3].end)
        self.assertAlmostEqual(seg.high, 12.8)
        self.assertAlmostEqual(seg.low, 9.2)
        self.assertAlmostEqual(seg.start_price, bis[0].start_price)
        self.assertAlmostEqual(seg.end_price, bis[3].end_price)

    def test_detect_zhongshus_creates_one_from_three_overlapping_segments(self):
        segments = [
            self._segment(1, "up", 0, 10, 110.0, 100.0),
            self._segment(2, "down", 11, 20, 108.0, 102.0),
            self._segment(3, "up", 21, 30, 109.0, 103.0),
        ]
        detector = SegmentDetector(bis=[])

        zhongshus = detector.detect_zhongshus(segments)
        self.assertEqual(len(zhongshus), 1)
        zs = zhongshus[0]
        self.assertEqual(zs.id, "zs_1")
        self.assertEqual(zs.start, segments[0].start)
        self.assertEqual(zs.end, segments[2].end)
        self.assertAlmostEqual(zs.range_high, 108.0)
        self.assertAlmostEqual(zs.range_low, 103.0)
        self.assertEqual(zs.xiang_ids, ["xiang_1", "xiang_2", "xiang_3"])

    def test_detect_zhongshus_extension_keeps_overlap_not_union(self):
        # 中枢延伸时区间应取所有段的交叠（收窄），而非并集扩张
        segments = [
            self._segment(1, "up", 0, 10, 110.0, 100.0),
            self._segment(2, "down", 11, 20, 108.0, 102.0),
            self._segment(3, "up", 21, 30, 109.0, 103.0),
            # 第4段向上突破但仍与中枢重叠：正确结果收窄到 [105, 108]，
            # 错误实现会扩张成 [103, 120]
            self._segment(4, "down", 31, 40, 120.0, 105.0),
        ]
        detector = SegmentDetector(bis=[])
        zhongshus = detector.detect_zhongshus(segments)

        self.assertEqual(len(zhongshus), 1)
        zs = zhongshus[0]
        self.assertAlmostEqual(zs.range_high, 108.0)
        self.assertAlmostEqual(zs.range_low, 105.0)
        self.assertEqual(zs.xiang_ids, ["xiang_1", "xiang_2", "xiang_3", "xiang_4"])

    def test_get_zhongshu_for_price_returns_latest_matching_zone(self):
        segments = [
            self._segment(1, "up", 0, 10, 110.0, 100.0),
            self._segment(2, "down", 11, 20, 108.0, 102.0),
            self._segment(3, "up", 21, 30, 109.0, 103.0),
            self._segment(4, "down", 31, 40, 130.0, 120.0),
            self._segment(5, "up", 41, 50, 128.0, 122.0),
            self._segment(6, "down", 51, 60, 126.0, 123.0),
        ]
        detector = SegmentDetector(bis=[])
        zhongshus = detector.detect_zhongshus(segments)

        self.assertEqual(len(zhongshus), 2)
        latest_match = detector.get_zhongshu_for_price(zhongshus, 124.0)
        self.assertIsNotNone(latest_match)
        self.assertEqual(latest_match.id, "zs_2")


if __name__ == "__main__":
    unittest.main()
