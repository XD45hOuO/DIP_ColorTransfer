"""
scale_space.py
--------------
建立論文中的「尺度空間直方圖」(Scale-space Histogram)。

公式:
    Smax = floor(log2(B / Bmin))

對於每一層 k (1 <= k <= Smax):
    1) 將直方圖以 bicubic 降採樣至 ceil(B / 2^k)
    2) 再以 nearest-neighbor 升採樣回原始長度 B
    這個「降-升」步驟相當於低通濾波, 隨 k 增加而保留越少高頻細節。
"""

from __future__ import annotations

import math
from typing import Tuple

import cv2
import numpy as np


def compute_smax(B: int, Bmin: int) -> int:
    """Smax = floor(log2(B / Bmin)). 最少回傳 1。"""
    if Bmin <= 0 or B <= Bmin:
        return 1
    return max(1, int(math.floor(math.log2(B / Bmin))))


def channel_histogram(channel: np.ndarray,
                      B: int,
                      value_range: Tuple[float, float]) -> np.ndarray:
    """
    將單通道資料離散成長度為 B 的直方圖 (float, 已歸一化為機率質量).
    """
    lo, hi = value_range
    flat = channel.reshape(-1)
    flat = np.clip(flat, lo, hi - 1e-6)
    hist, _ = np.histogram(flat, bins=B, range=(lo, hi))
    hist = hist.astype(np.float64)
    s = hist.sum()
    if s > 0:
        hist /= s
    return hist


def smooth_histogram_at_scale(hist: np.ndarray, k: int, Smax: int) -> np.ndarray:
    """
    將長度 B 的直方圖平滑到尺度 k (依論文 Eq. 7 附近的定義).

        B_k = B * 2^(k - Smax)
        k = 1     -> 最粗尺度 (B_k = B / 2^(Smax-1), 接近 Bmin)
        k = Smax  -> 最細尺度 (B_k = B, 不平滑)

    流程:
        down: bicubic 到 B_k
        up  : nearest 回 B
    """
    B = hist.shape[0]
    if k >= Smax:
        return hist.copy()

    down_len = max(2, int(math.ceil(B / (2 ** (Smax - k)))))

    row = hist.astype(np.float32).reshape(1, B)

    # Step 1: 降採樣 (bicubic)
    row_down = cv2.resize(row, (down_len, 1), interpolation=cv2.INTER_CUBIC)

    # Step 2: 升採樣 (nearest)
    row_up = cv2.resize(row_down, (B, 1), interpolation=cv2.INTER_NEAREST)

    smoothed = row_up.reshape(B).astype(np.float64)

    # bicubic 會產生負值, 截斷後重新歸一化以維持機率性質
    smoothed = np.clip(smoothed, 0.0, None)
    s = smoothed.sum()
    if s > 0:
        smoothed /= s
    return smoothed


def build_scale_space(hist: np.ndarray, Smax: int) -> list:
    """
    回傳長度 Smax+1 的 list:
        index 0  : 原始未平滑直方圖 (= hist)
        index k  : 尺度 k (1=粗, Smax=細)
    """
    pyramid = [hist.copy()]
    for k in range(1, Smax + 1):
        pyramid.append(smooth_histogram_at_scale(hist, k, Smax))
    return pyramid
