"""
detail_preserve.py
------------------
依論文 Eq. (16)(17) 做雙邊濾波細節保留。

    I_res   = I - bilateral(I)                       (Eq. 16)
    I_o'    = I_o + w_c · (I_res,s - I_res,o)        (Eq. 17)

論文明確指出:
    "This process is carried out for each channel separately."
故此模組對 L, a, b 三通道皆可呼叫。
"""

from __future__ import annotations

import cv2
import numpy as np


def bilateral_filter(chan: np.ndarray,
                     d: int = 9,
                     sigma_color: float = 25.0,
                     sigma_space: float = 25.0) -> np.ndarray:
    """單通道 bilateral filter (float32)."""
    return cv2.bilateralFilter(chan.astype(np.float32),
                               d, sigma_color, sigma_space)


def detail_residual(chan: np.ndarray,
                    d: int = 9,
                    sigma_color: float = 25.0,
                    sigma_space: float = 25.0) -> np.ndarray:
    """Eq. 16:  I_res = I - bilateral(I)."""
    smooth = bilateral_filter(chan, d, sigma_color, sigma_space)
    return chan.astype(np.float32) - smooth


def apply_detail_preserve(chan_out: np.ndarray,
                          res_src: np.ndarray,
                          res_out: np.ndarray,
                          w_c: float = 1.0,
                          value_range=(0.0, 100.0)) -> np.ndarray:
    """
    Eq. 17:  I_o' = I_o + w_c * (I_res,s - I_res,o)
    並截斷至該通道合法範圍。
    """
    enhanced = chan_out + w_c * (res_src - res_out)
    lo, hi = value_range
    return np.clip(enhanced, lo, hi).astype(np.float32)


# --- 向後相容: 舊呼叫 bilateral_L ---
def bilateral_L(L_channel: np.ndarray,
                d: int = 9,
                sigma_color: float = 25.0,
                sigma_space: float = 25.0) -> np.ndarray:
    return bilateral_filter(L_channel, d, sigma_color, sigma_space)
