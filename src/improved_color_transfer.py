"""
improved_color_transfer.py
--------------------------
Saliency-weighted Progressive Color Transfer
(本專案在論文 Pouli & Reinhard 2011 之上提出的改良方法)

=== 動機 ===
論文方法用單一全域 perc 控制整張影像的色彩轉移強度,
對「主體」和「背景」一視同仁。在以下情境會產生不自然的結果:
    - source: 草地上的白虎; target: 紅色番茄堆
      → 論文方法: 整張變橘紅, 連白虎也被染紅
      → 改良方法: 白虎保留原色, 草地背景轉成番茄紅, 整體氛圍切換但主體完整

=== 演算法 ===
步驟 1: 跑論文標準 pipeline 得到 paper_out (全域全強度轉移後的影像).
步驟 2: 用 Hou & Zhang (2007) Spectral Residual 偵測 source 的 saliency map S(p).
步驟 3: 將 saliency 線性映射為 per-pixel 轉移強度:
            α(p) = α_bg + (α_salient − α_bg) · S(p)
步驟 4: 在 CIELab 空間做 per-pixel 漸進混合 (避免 RGB 加權的非感知均勻問題):
            out_Lab(p) = (1 − α(p)) · src_Lab(p) + α(p) · paper_Lab(p)
            out_RGB    = Lab → RGB
步驟 5: 將 saliency map / α map / 4-panel 對比圖落地, 便於報告比較。

=== 與論文 Sec. 4 (Region Selection) 的關聯 ===
論文用 Soft Scissors 手繪 matte 達成類似效果, 但需要使用者輸入。
本方法將「matte 自動化」, 把 region selection 的負擔從使用者轉移到演算法,
等同於補上論文留下的人工依賴 (限制條件之一).

=== 參數預設 ===
    α_salient    = 0.5   (主體弱轉移, 保留原色 50%)
    α_background = 1.0   (背景全轉移)
    target_size  = 64    (saliency 計算尺寸; 64 對任意圖都夠用且快速)
"""

from __future__ import annotations

import os
from typing import Dict, Tuple

import numpy as np

from config import TransferConfig
from src.color_space import rgb_to_lab, lab_to_rgb
from src.transfer import progressive_color_transfer
from src.saliency import compute_saliency, saliency_to_alpha
from src.visualize import ensure_dir, plot_triplet


# --------------------------------------------------------------------- #
#  主要 API
# --------------------------------------------------------------------- #
def improved_color_transfer(src_rgb: np.ndarray,
                            tgt_rgb: np.ndarray,
                            cfg: TransferConfig,
                            alpha_salient: float = 0.5,
                            alpha_background: float = 1.0,
                            saliency_size: int = 64,
                            saliency_smooth_sigma: float = 8.0,
                            save_prefix: str = "run_improved"
                            ) -> Tuple[np.ndarray, Dict]:
    """
    執行 saliency-weighted color transfer.

    Args:
        src_rgb, tgt_rgb:     輸入影像 (uint8 RGB).
        cfg:                  TransferConfig (用於底層論文 pipeline).
        alpha_salient:        主體區域的轉移強度 (預設 0.5 = 保留 50% 原色).
        alpha_background:     背景區域的轉移強度 (預設 1.0 = 完全採用 target).
        saliency_size:        saliency 計算尺寸 (短邊上限).
        saliency_smooth_sigma: saliency map 平滑度.
        save_prefix:          中間檔案前綴.

    Returns:
        (out_rgb, debug_dict)
    """
    # ---- 1) 跑論文 pipeline ----
    paper_out, paper_debug = progressive_color_transfer(
        src_rgb, tgt_rgb, cfg, save_prefix=f"{save_prefix}_paper"
    )

    # ---- 2) Saliency 偵測 (來自 source) ----
    saliency = compute_saliency(
        src_rgb,
        target_size=saliency_size,
        smooth_sigma=saliency_smooth_sigma,
    )

    # ---- 3) per-pixel 轉移強度 ----
    alpha = saliency_to_alpha(
        saliency,
        alpha_salient=alpha_salient,
        alpha_background=alpha_background,
    )

    # ---- 4) Lab 空間 per-pixel 混合 ----
    src_lab = rgb_to_lab(src_rgb)
    paper_lab = rgb_to_lab(paper_out)
    alpha_3 = alpha[..., None]
    out_lab = (1.0 - alpha_3) * src_lab + alpha_3 * paper_lab
    out_rgb = lab_to_rgb(out_lab)

    # ---- 5) 視覺化 ----
    if cfg.save_intermediate and save_prefix:
        _save_improved_visualizations(
            src_rgb, tgt_rgb, paper_out, out_rgb,
            saliency, alpha,
            cfg.intermediate_dir, save_prefix,
        )

    debug = {
        "paper_debug": paper_debug,
        "paper_out": paper_out,
        "saliency": saliency,
        "alpha_map": alpha,
        "alpha_salient": alpha_salient,
        "alpha_background": alpha_background,
    }
    return out_rgb, debug


# --------------------------------------------------------------------- #
#  視覺化輔助
# --------------------------------------------------------------------- #
def _save_improved_visualizations(src_rgb, tgt_rgb, paper_out, improved_out,
                                  saliency, alpha,
                                  intermediate_dir: str,
                                  prefix: str) -> None:
    """落地 saliency map / alpha map / 4-panel 對比."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ensure_dir(intermediate_dir)

    # --- (a) saliency map 視覺化 (灰階) ---
    sal_path = os.path.join(intermediate_dir, f"{prefix}_saliency.png")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].imshow(src_rgb); axes[0].set_title("Source"); axes[0].axis("off")
    im = axes[1].imshow(saliency, cmap="hot", vmin=0, vmax=1)
    axes[1].set_title("Saliency map (Spectral Residual)")
    axes[1].axis("off")
    fig.colorbar(im, ax=axes[1], fraction=0.04)
    fig.tight_layout()
    fig.savefig(sal_path, dpi=130)
    plt.close(fig)

    # --- (b) alpha 轉移強度地圖 ---
    alpha_path = os.path.join(intermediate_dir, f"{prefix}_alpha.png")
    fig, ax = plt.subplots(1, 1, figsize=(6, 5))
    im = ax.imshow(alpha, cmap="viridis", vmin=0, vmax=1)
    ax.set_title(r"per-pixel transfer strength $\alpha(p)$")
    ax.axis("off")
    fig.colorbar(im, ax=ax, fraction=0.04, label=r"$\alpha$")
    fig.tight_layout()
    fig.savefig(alpha_path, dpi=130)
    plt.close(fig)

    # --- (c) 4-panel ablation: src | tgt | paper | improved ---
    cmp_path = os.path.join(intermediate_dir, f"{prefix}_4panel.png")
    fig, axes = plt.subplots(1, 4, figsize=(16, 4))
    titles = ["Source", "Target", "Paper method", "Improved (saliency-weighted)"]
    images = [src_rgb, tgt_rgb, paper_out, improved_out]
    for ax, im, t in zip(axes, images, titles):
        ax.imshow(im); ax.set_title(t); ax.axis("off")
    fig.suptitle("Ablation: paper baseline vs. saliency-weighted improvement")
    fig.tight_layout()
    fig.savefig(cmp_path, dpi=140)
    plt.close(fig)


# --------------------------------------------------------------------- #
#  方便外部直接呼叫的封裝
# --------------------------------------------------------------------- #
def run_both_and_compare(src_rgb: np.ndarray,
                         tgt_rgb: np.ndarray,
                         cfg: TransferConfig,
                         alpha_salient: float = 0.5,
                         alpha_background: float = 1.0,
                         save_prefix: str = "compare") -> Dict:
    """
    同時跑論文方法與改良方法, 將 4-panel 對比圖落地至 final_dir。
    回傳 dict 包含 paper_out / improved_out / saliency / alpha.
    """
    improved_out, dbg = improved_color_transfer(
        src_rgb, tgt_rgb, cfg,
        alpha_salient=alpha_salient,
        alpha_background=alpha_background,
        save_prefix=save_prefix,
    )

    # 主結果三聯比較 (Source / Target / Improved)
    ensure_dir(cfg.final_dir)
    triplet_path = os.path.join(cfg.final_dir, f"{save_prefix}_improved_triplet.png")
    plot_triplet(src_rgb, tgt_rgb, improved_out, triplet_path,
                 suptitle=(f"Improved (saliency-weighted)  "
                           f"α_sal={alpha_salient}, α_bg={alpha_background}"))

    return {
        "paper_out": dbg["paper_out"],
        "improved_out": improved_out,
        "saliency": dbg["saliency"],
        "alpha_map": dbg["alpha_map"],
        "triplet_path": triplet_path,
    }
