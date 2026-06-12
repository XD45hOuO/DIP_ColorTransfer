"""
feature_detection.py
--------------------
從平滑後的直方圖找出「區域 (regions)」。

論文定義: 區域邊界由直方圖的局部極小值 (local minima) 劃分,
偵測方式為一階導數變號 + 二階導數 > 0。

回傳形式:
    regions = [(start_bin, end_bin), ...]  # 半開區間 [start, end)
"""

from __future__ import annotations

from typing import List, Tuple

import numpy as np


def _first_derivative(h: np.ndarray) -> np.ndarray:
    """中央差分一階導數, 兩端以前/後向差分補足."""
    d = np.zeros_like(h)
    d[1:-1] = (h[2:] - h[:-2]) / 2.0
    d[0] = h[1] - h[0]
    d[-1] = h[-1] - h[-2]
    return d


def _second_derivative(h: np.ndarray) -> np.ndarray:
    """中央差分二階導數."""
    d2 = np.zeros_like(h)
    d2[1:-1] = h[2:] - 2.0 * h[1:-1] + h[:-2]
    d2[0] = d2[1]
    d2[-1] = d2[-2]
    return d2


def find_minima(hist: np.ndarray, min_distance: int = 4) -> List[int]:
    """
    尋找直方圖局部極小值 bin 索引。

    判定:
        d1[i-1] <= 0 且 d1[i+1] >= 0  (一階變號, 由負轉正)
        d2[i] > 0                     (二階為正 = 凹向上)

    並執行非極大抑制 (min_distance), 過濾過近的極小值。
    """
    B = hist.shape[0]
    d1 = _first_derivative(hist)
    d2 = _second_derivative(hist)

    candidates = []
    for i in range(1, B - 1):
        if d1[i - 1] <= 0.0 and d1[i + 1] >= 0.0 and d2[i] > 0.0:
            candidates.append(i)

    if not candidates:
        return []

    # 依直方圖值由低到高排序 (越低的 minima 越「乾淨」), 進行 NMS
    candidates.sort(key=lambda idx: hist[idx])
    kept: List[int] = []
    for idx in candidates:
        if all(abs(idx - k) >= min_distance for k in kept):
            kept.append(idx)
    kept.sort()
    return kept


def split_regions(hist_length: int,
                  minima: List[int]) -> List[Tuple[int, int]]:
    """
    將 [0, hist_length) 用 minima 切成多個半開區間。
    若無 minima 則整段視為一個區域。
    """
    if not minima:
        return [(0, hist_length)]
    boundaries = [0] + sorted(minima) + [hist_length]
    regions = []
    for i in range(len(boundaries) - 1):
        s, e = boundaries[i], boundaries[i + 1]
        if e - s > 1:
            regions.append((s, e))
    return regions


def detect_regions(hist: np.ndarray,
                   min_distance: int = 4) -> List[Tuple[int, int]]:
    """高階介面: 直方圖 -> 區段列表."""
    minima = find_minima(hist, min_distance=min_distance)
    return split_regions(hist.shape[0], minima)
