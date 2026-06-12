"""
histogram_matching.py
---------------------
利用累積分布函數 (CDF) 將「原始通道數值」映射到「目標重塑直方圖」。

流程:
    1) 將 source channel 離散為 B-bin 直方圖, 取 CDF -> CDF_s
    2) 取得目標重塑直方圖 ho 的 CDF -> CDF_o
    3) 對每個 source bin i, 找到最小的 j 使得 CDF_o[j] >= CDF_s[i]
    4) 用此查找表將每個 source pixel 映射至新 bin 中心值
"""

from __future__ import annotations

from typing import Tuple

import numpy as np


def _bin_centers(B: int, value_range: Tuple[float, float]) -> np.ndarray:
    lo, hi = value_range
    edges = np.linspace(lo, hi, B + 1)
    return 0.5 * (edges[:-1] + edges[1:])


def _bin_index(values: np.ndarray, B: int,
               value_range: Tuple[float, float]) -> np.ndarray:
    lo, hi = value_range
    clipped = np.clip(values, lo, hi - 1e-6)
    idx = ((clipped - lo) / (hi - lo) * B).astype(np.int64)
    return np.clip(idx, 0, B - 1)


def match_channel_to_histogram(channel: np.ndarray,
                               src_hist: np.ndarray,
                               target_hist: np.ndarray,
                               value_range: Tuple[float, float]) -> np.ndarray:
    """
    將 channel 的像素值依 src->target 直方圖做 CDF 對齊。

    Args:
        channel:      H x W, float, 原始 source channel.
        src_hist:     長度 B, source 的「原始」(尺度 0) 直方圖 (機率).
        target_hist:  長度 B, 重塑後的目標直方圖 (機率).
        value_range:  (lo, hi), 通道值域.

    Returns:
        H x W, float, 已重新映射的 channel.
    """
    B = src_hist.shape[0]
    centers = _bin_centers(B, value_range)

    # CDF
    cdf_s = np.cumsum(src_hist)
    cdf_o = np.cumsum(target_hist)
    # 數值保護
    if cdf_s[-1] > 0:
        cdf_s = cdf_s / cdf_s[-1]
    if cdf_o[-1] > 0:
        cdf_o = cdf_o / cdf_o[-1]

    # 對每個 source bin i, 找 CDF_o 中第一個 >= CDF_s[i] 的位置
    # 使用 searchsorted 加速 (O(B log B))
    lut = np.searchsorted(cdf_o, cdf_s, side="left")
    lut = np.clip(lut, 0, B - 1)

    # 將 channel 像素 -> bin index -> LUT -> bin center
    src_bins = _bin_index(channel, B, value_range)
    new_bins = lut[src_bins]
    return centers[new_bins].astype(np.float32)


def blend_with_perc(original: np.ndarray,
                    matched: np.ndarray,
                    perc: float) -> np.ndarray:
    """
    使用者可控的「轉移百分比」線性內插:
        out = (1 - perc) * original + perc * matched
    """
    perc = float(np.clip(perc, 0.0, 1.0))
    return (1.0 - perc) * original + perc * matched
