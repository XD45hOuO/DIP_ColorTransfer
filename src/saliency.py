"""
saliency.py
-----------
自動視覺顯著性 (Saliency) 偵測 - Hou & Zhang (2007) Spectral Residual.

原理:
    1. 將影像降採樣至小尺寸 (預設 64px), 大幅加速 FFT
    2. 計算 log spectrum L = log(|FFT(I)| + ε)
    3. Spectral residual R = L - avgfilter(L, 3x3)
       (一般場景的 log spectrum 接近線性, 殘差代表「不尋常」處)
    4. 重建 saliency: S = |IFFT(exp(R + i·phase))|^2
    5. Gaussian 平滑 + 線性歸一化到 [0, 1]
    6. 上採樣回原始解析度

優點: 無需訓練、純 FFT 計算、對任意輸入皆有效。
"""

from __future__ import annotations

import cv2
import numpy as np


# --------------------------------------------------------------------- #
#  Core spectral residual                                               #
# --------------------------------------------------------------------- #
def _spectral_residual(gray_small: np.ndarray, eps: float = 1e-8) -> np.ndarray:
    """對單張小尺寸灰階影像計算 spectral residual saliency."""
    f = np.fft.fft2(gray_small)
    mag = np.abs(f)
    phase = np.angle(f)

    log_mag = np.log(mag + eps)
    # 3x3 均值濾波 (在 log spectrum 上估計「整體趨勢」)
    avg = cv2.boxFilter(log_mag.astype(np.float32), ddepth=-1, ksize=(3, 3))
    residual = log_mag - avg

    # 重建: 用殘差幅值 + 原始相位
    f_recon = np.exp(residual) * np.exp(1j * phase)
    sal = np.abs(np.fft.ifft2(f_recon)) ** 2
    return sal.astype(np.float32)


# --------------------------------------------------------------------- #
#  Public API                                                           #
# --------------------------------------------------------------------- #
def compute_saliency(img_rgb: np.ndarray,
                     target_size: int = 64,
                     smooth_sigma: float = 8.0) -> np.ndarray:
    """
    從 RGB 影像生成 [0,1] saliency map。

    Args:
        img_rgb:       H x W x 3 uint8 RGB.
        target_size:   降採樣後較長邊的目標 px 數 (預設 64).
        smooth_sigma:  Gaussian 平滑強度 (在小尺寸圖上計算).

    Returns:
        H x W float32 in [0,1]; 高值代表「視覺顯著 (主體)」。
    """
    h, w = img_rgb.shape[:2]
    scale = float(target_size) / float(max(h, w))
    small_size = (max(8, int(round(w * scale))),
                  max(8, int(round(h * scale))))

    small = cv2.resize(img_rgb, small_size, interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0

    sal_small = _spectral_residual(gray)

    ksize = max(3, int(6 * smooth_sigma) | 1)
    sal_small = cv2.GaussianBlur(sal_small, (ksize, ksize), smooth_sigma)

    # 上採樣回原始大小
    sal = cv2.resize(sal_small, (w, h), interpolation=cv2.INTER_CUBIC)

    # 線性歸一化到 [0,1]
    sal_min = float(sal.min())
    sal -= sal_min
    sal_max = float(sal.max())
    if sal_max > 0:
        sal /= sal_max
    return sal.astype(np.float32)


def saliency_to_alpha(saliency: np.ndarray,
                      alpha_salient: float = 0.5,
                      alpha_background: float = 1.0) -> np.ndarray:
    """
    將 saliency 線性映射為「per-pixel 轉移強度」α(p)。

        α(p) = α_bg + (α_salient − α_bg) · S(p)

    預設 α_salient=0.5、α_bg=1.0:
        主體 (S→1):  α=0.5 → 弱轉移, 保留 source 個性
        背景 (S→0):  α=1.0 → 全轉移, 採用 target 色調
    """
    alpha = alpha_background + (alpha_salient - alpha_background) * saliency
    return np.clip(alpha, 0.0, 1.0).astype(np.float32)
