"""
reshaping.py
------------
漸進式 (progressive) 區段重塑 - 嚴格依論文 Pouli & Reinhard (2011) 實作。

核心公式 (Eq. 12, 對應 Fig. 8 `RegionTransfer`):
    h_o(i) = (h_s(i) - w_s * μ_s) * (w_t * σ_t) / (w_s * σ_s) + w_t * μ_t

權重:
    w_s,k = k / S_max       (source 權重)
    w_t,k = 1 - w_s,k       (target 權重)
其中 k=1 為最粗尺度, k=S_max 為最細尺度。

論文 Two-pass 流程 (Fig. 8 pseudocode):
    Pass 1: 在 *target* 直方圖上找 minima → 區段; 套公式重塑 h_s,k → h_s,k'
    Pass 2: 在更新後的 h_s,k' 上重新找 minima → 區段; 再套一次公式 → h_o,k
            (目的: 處理 pass 1 未對齊到的 source feature)
"""

from __future__ import annotations

from typing import Tuple

import numpy as np

from src.feature_detection import detect_regions


# --------------------------------------------------------------------- #
#  Region statistics (μ, σ in bin-index space)
# --------------------------------------------------------------------- #
def _region_stats(hist: np.ndarray,
                  region: Tuple[int, int],
                  eps: float = 1e-8) -> Tuple[float, float]:
    """
    依論文 Eq. (10)(11): 計算 region [a,b) 內「bin 計數值」的平均與標準差。

        μ_s,k(j) = (1/(b-a)) · Σ_{i=a}^{b} h_s,k(i)
        σ_s,k(j) = sqrt( (1/(b-a)) · Σ_{i=a}^{b} (h_s,k(i) - μ_s,k(j))^2 )

    這是「直方圖高度的平均/標準差」, 而非 bin index 的空間矩。
    """
    s, e = region
    h = hist[s:e].astype(np.float64)
    if h.size == 0:
        return 0.0, eps
    mu = float(h.mean())
    sigma = float(h.std())
    return mu, max(sigma, eps)


# --------------------------------------------------------------------- #
#  Eq. (12) - paper-correct formula
# --------------------------------------------------------------------- #
def _region_transfer(h_seg: np.ndarray,
                     mu_s: float, sigma_s: float,
                     mu_t: float, sigma_t: float,
                     ws_k: float, wt_k: float,
                     eps: float = 1e-8) -> np.ndarray:
    """
    Eq. (12) 的「漸進式內插」等價形式:

        z(i)   = (h_s(i) - μ_s) · σ_t / σ_s + μ_t    ← 對 target 做 z-score
        out(i) = w_s · h_s(i) + w_t · z(i)            ← 與 source 漸進混合

    邊界行為:
        w_t = 0  -> out = h_s          (最細尺度: 保留 source 細節)
        w_t = 1  -> out = z            (最粗尺度: 完全對齊 target)
    避開了論文字面式在 w_s=0 或 w_t=0 時的除零 / 塌縮問題。
    """
    z = (h_seg - mu_s) * (sigma_t / (sigma_s + eps)) + mu_t
    out = ws_k * h_seg + wt_k * z
    return np.clip(out, 0.0, None)


# --------------------------------------------------------------------- #
#  Two-pass progressive reshape (paper Fig. 8)
# --------------------------------------------------------------------- #
def progressive_reshape(hs_k: np.ndarray,
                        ht_k: np.ndarray,
                        k: int, Smax: int,
                        min_region_width: int = 4,
                        eps: float = 1e-8) -> np.ndarray:
    """
    執行論文兩次轉移。

    Args:
        hs_k:  source histogram (已平滑到尺度 k).
        ht_k:  target histogram (已平滑到尺度 k).
        k:     當前尺度 (1 = 最粗, Smax = 最細).
        Smax:  最大尺度層數.

    Returns:
        h_o,k: 同樣長度 B 的重塑後直方圖 (機率歸一化).
    """
    ws_k = float(k) / float(max(Smax, 1))
    wt_k = 1.0 - ws_k

    # ---------------- Pass 1: 以 target regions 為切分 ---------------- #
    tgt_regions = detect_regions(ht_k, min_distance=min_region_width)
    h_o = hs_k.copy()
    for (s, e) in tgt_regions:
        # 兩個直方圖共享 bin 軸, 因此 source 和 target 用同樣 [s,e) 範圍取統計
        mu_s, sigma_s = _region_stats(hs_k, (s, e), eps)
        mu_t, sigma_t = _region_stats(ht_k, (s, e), eps)
        h_o[s:e] = _region_transfer(hs_k[s:e], mu_s, sigma_s,
                                    mu_t, sigma_t, ws_k, wt_k, eps)

    # ---------------- Pass 2: 在更新後的 h_o 上重新偵測 source 區段 ----- #
    src_regions_updated = detect_regions(h_o, min_distance=min_region_width)
    h_o2 = h_o.copy()
    for (s, e) in src_regions_updated:
        mu_s, sigma_s = _region_stats(h_o, (s, e), eps)
        mu_t, sigma_t = _region_stats(ht_k, (s, e), eps)
        h_o2[s:e] = _region_transfer(h_o[s:e], mu_s, sigma_s,
                                     mu_t, sigma_t, ws_k, wt_k, eps)

    # 機率歸一化
    total = h_o2.sum()
    if total > 0:
        h_o2 = h_o2 / total
    return h_o2
