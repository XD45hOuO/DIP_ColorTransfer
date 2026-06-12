"""
achromatic.py
-------------
無彩色錨定 (Achromatic Anchoring) - 嚴格依論文 Eq. (18) 實作。

論文流程:
    1) 對每個色度通道 c ∈ {a, b}, 建立遮罩
            M_c(p) = 1, if |c_src(p)| > w_a · (max(c)-min(c))   (有彩)
                     0, otherwise                                 (無彩)
    2) 無彩色遮罩 = (1 - M_a) ∧ (1 - M_b)
    3) 將遮罩做 Gaussian 平滑, 避免硬邊界。
    4) 「位移」: Δa = a_out - a_src,  Δb = b_out - b_src
       校正:    a_final = a_out - mask_soft · Δa
                b_final = b_out - mask_soft · Δb
       對純無彩色像素 (mask=1) 等價於將 a,b 拉回原始值;
       對純有彩像素 (mask=0) 不做任何修正; 邊緣處平滑過渡。
"""

from __future__ import annotations

from typing import Tuple

import cv2
import numpy as np


def _channel_range(chan: np.ndarray, eps: float = 1e-6) -> float:
    """Eq. 18 中的 max(l) - min(l)."""
    r = float(chan.max() - chan.min())
    return max(r, eps)


def build_achromatic_mask(a_src: np.ndarray,
                          b_src: np.ndarray,
                          wa: float = 0.08,
                          gauss_sigma: float = 3.0) -> np.ndarray:
    """
    回傳 H x W float32 的軟遮罩, 1 = 無彩色 (應錨定回 source), 0 = 有彩色。
    """
    a_range = _channel_range(a_src)
    b_range = _channel_range(b_src)

    M_a = (np.abs(a_src) > wa * a_range)            # True = 有彩 (a)
    M_b = (np.abs(b_src) > wa * b_range)            # True = 有彩 (b)
    achr = (~(M_a | M_b)).astype(np.float32)        # 兩個皆無彩才算無彩

    ksize = max(3, int(6 * gauss_sigma) | 1)
    achr_soft = cv2.GaussianBlur(achr, (ksize, ksize), gauss_sigma)
    return achr_soft


def apply_achromatic_anchor(a_src: np.ndarray, b_src: np.ndarray,
                            a_out: np.ndarray, b_out: np.ndarray,
                            mask_soft: np.ndarray
                            ) -> Tuple[np.ndarray, np.ndarray]:
    """
    依論文「位移補償」做色彩錨定:
        Δa = a_out - a_src,    Δb = b_out - b_src
        a_final = a_out - mask · Δa
        b_final = b_out - mask · Δb
    """
    da = a_out - a_src
    db = b_out - b_src
    a_final = a_out - mask_soft * da
    b_final = b_out - mask_soft * db
    return a_final.astype(np.float32), b_final.astype(np.float32)


# --------------------------------------------------------------------- #
#  舊 API 別名 (向後相容 transfer.py 之前的呼叫)
# --------------------------------------------------------------------- #
def achromatic_mask(a_src: np.ndarray, b_src: np.ndarray,
                    wa: float = 0.08, gauss_sigma: float = 3.0,
                    ab_max_range: float = 128.0) -> np.ndarray:
    """已棄用, 改呼叫 build_achromatic_mask (參數 ab_max_range 忽略)."""
    return build_achromatic_mask(a_src, b_src, wa=wa, gauss_sigma=gauss_sigma)
