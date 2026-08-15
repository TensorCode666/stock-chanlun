"""
线段与中枢检测器
"""
from typing import Optional
from datetime import datetime
from .elements import Bi, XiangSegment, Zhongshu


class SegmentDetector:
    """
    线段规则:
    - 3笔（或以上）重叠构成线段
    - 线段被更高一级别笔破坏则线段结束

    中枢规则:
    - 3个（或以上）连续同级别线段的重叠区域构成中枢
    """

    def __init__(self, bis: list[Bi]):
        self.bis = bis

    def detect_segments(self, min_overlap_bis: int = 3, max_iterations: int = 10000) -> list[XiangSegment]:
        """检测线段"""
        if len(self.bis) < 3:
            return []

        segments: list[XiangSegment] = []
        i = 0
        iterations = 0

        while i <= len(self.bis) - min_overlap_bis:
            # 防止死循环
            iterations += 1
            if iterations > max_iterations:
                break

            # 取连续3笔检查重叠
            group = self.bis[i:i + min_overlap_bis]
            if self._has_overlap(group):
                # 检查是否可延伸
                start = group[0].start
                end = group[-1].end
                direction = group[0].direction
                high = max(b.high for b in group)
                low = min(b.low for b in group)
                start_price = group[0].start_price
                end_price = group[-1].end_price
                bi_ids = [b.id for b in group]

                # 尝试延伸
                extended = True
                extend_iterations = 0
                while extended and extend_iterations < 1000:
                    extended = False
                    extend_iterations += 1
                    # 依据当前已并入的笔数量推进索引，避免重复读取同一根笔
                    next_idx = i + len(bi_ids)
                    if next_idx < len(self.bis):
                        next_b = self.bis[next_idx]
                        if next_b.direction == direction:
                            if self._overlaps(next_b, high, low):
                                high = max(high, next_b.high)
                                low = min(low, next_b.low)
                                bi_ids.append(next_b.id)
                                end = next_b.end
                                end_price = next_b.end_price
                                extended = True

                segments.append(XiangSegment(
                    id=f"xiang_{len(segments)+1}",
                    start=start,
                    end=end,
                    direction=direction,
                    high=high,
                    low=low,
                    start_price=start_price,
                    end_price=end_price,
                    bi_ids=bi_ids,
                    level=2
                ))
                i += len(bi_ids)
            else:
                i += 1

        return segments

    def _has_overlap(self, bis_group: list[Bi]) -> bool:
        """判断一组笔是否有重叠"""
        if len(bis_group) < 2:
            return False
        high = min(b.high for b in bis_group)
        low = max(b.low for b in bis_group)
        return high > low  # 有重叠区域

    def _overlaps(self, bi: Bi, existing_high: float, existing_low: float) -> bool:
        """判断笔是否与已有区域重叠"""
        return bi.high > existing_low and bi.low < existing_high

    def detect_zhongshus(self, segments: list[XiangSegment]) -> list[Zhongshu]:
        """
        检测中枢（滑动窗口算法）：
        遍历线段序列，每取得连续3段计算重叠区间：
        - 有重叠 → 构成中枢，尝试向后延伸（后续线段若与之重叠则并入）
        - 无重叠 → 跳过，继续寻找下一组
        相邻中枢之间必然间隔至少3个线段，不会重复。
        """
        if len(segments) < 3:
            return []

        zhongshus: list[Zhongshu] = []
        i = 0

        while i <= len(segments) - 3:
            group = segments[i:i + 3]

            # 计算三段重叠区间
            range_high = min(s.high for s in group)
            range_low = max(s.low for s in group)

            if range_high > range_low:
                # 重叠 → 形成中枢，尝试向后延伸
                cur_start = group[0].start
                cur_end = group[-1].end
                xiang_ids = [s.id for s in group]
                extend_idx = i + 3

                while extend_idx < len(segments):
                    nxt = segments[extend_idx]
                    # 新段与当前中枢重叠 → 并入；中枢区间取所有段的交叠（收窄），而非并集
                    if nxt.high > range_low and nxt.low < range_high:
                        range_high = min(range_high, nxt.high)
                        range_low = max(range_low, nxt.low)
                        cur_end = nxt.end
                        xiang_ids.append(nxt.id)
                        extend_idx += 1
                    else:
                        break

                zhongshus.append(Zhongshu(
                    id=f"zs_{len(zhongshus)+1}",
                    start=cur_start,
                    end=cur_end,
                    range_high=float(range_high),
                    range_low=float(range_low),
                    xiang_ids=xiang_ids,
                    level=group[0].level
                ))
                i = extend_idx  # 跳到中枢结束后的第一个线段
            else:
                i += 1

        return zhongshus

    def get_zhongshu_for_price(self, zhongshus: list[Zhongshu],
                                 price: float) -> Optional[Zhongshu]:
        """找到价格所在的中枢"""
        for zs in reversed(zhongshus):
            if zs.range_low <= price <= zs.range_high:
                return zs
        return None
