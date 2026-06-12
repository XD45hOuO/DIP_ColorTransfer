"""
config.py
---------
集中管理 progressive color transfer 演算法的預設超參數。
所有數值皆對應論文中的符號 (B, Bmin, wa, wc, etc.)。
"""

from dataclasses import dataclass, field
from typing import Tuple


@dataclass
class TransferConfig:
    # --- 直方圖相關 ---
    B: int = 400          # 直方圖 bin 數量 (論文預設)
    Bmin: int = 10        # 最小 bin 數量, 用以決定最大尺度層級

    # --- 漸進式轉移百分比 (0.0 ~ 1.0) ---
    perc: float = 1.0     # 1.0 = 完整轉移 target 色調；0.5 = 半轉移

    # --- 細節保留 (Bilateral filter + 殘差) ---
    bilat_d: int = 9              # 鄰域直徑
    bilat_sigma_color: float = 25 # 色彩域 sigma (Lab 尺度)
    bilat_sigma_space: float = 25 # 空間域 sigma
    w_c: float = 1.0              # 殘差混合權重 (論文 w_c)

    # --- 無彩色錨定 (Achromatic anchoring) ---
    wa: float = 0.08             # a,b 通道無彩色閾值比例
    achr_gauss_sigma: float = 3  # 遮罩高斯模糊 sigma

    # --- Lab 通道理論範圍 (D65, 8-bit input) ---
    L_range: Tuple[float, float] = (0.0, 100.0)
    a_range: Tuple[float, float] = (-128.0, 127.0)
    b_range: Tuple[float, float] = (-128.0, 127.0)

    # --- 視覺化 / 輸出控制 ---
    save_intermediate: bool = True
    intermediate_dir: str = "results/intermediate"
    final_dir: str = "results/final"

    # --- 區域偵測 (避免雜訊極小值) ---
    min_region_width: int = 4    # 兩個 minima 之間最小距離 (bin)
    eps: float = 1e-8            # 數值穩定常數


DEFAULT_CONFIG = TransferConfig()
