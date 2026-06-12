"""
transfer.py
-----------
Progressive color transfer 的主要 pipeline (paper-correct 版本).

對應論文 Fig. 8 pseudocode:
    function Transfer(Is, It, perc):
        Convert Is, It → CIELab
        Compute Smax = ⌊log2(B/Bmin)⌋
        for each channel:
            Compute Ds, Dt
            for k in 1 .. ⌊perc·Smax⌋:        # perc 控制使用的尺度數
                Ds,k = smooth(Ds_current, k)  # Ds_current 隨 k 累積更新
                Dt,k = smooth(Dt, k)
                Do,k = ProgressiveReshape(Ds,k, Dt,k, k)
                Ds_current ← Do,k             # 更新 source
            Io(c) = HistMatch(Is(c), Ds_current)
        Bilateral detail control (per channel, Eq. 16-17)
        Achromatic anchoring (Eq. 18)
        Convert back to RGB
"""

from __future__ import annotations

import os
from typing import Dict, Tuple

import numpy as np

from config import TransferConfig
from src.color_space import rgb_to_lab, lab_to_rgb
from src.scale_space import (
    compute_smax, channel_histogram, smooth_histogram_at_scale,
    build_scale_space,
)
from src.feature_detection import detect_regions
from src.reshaping import progressive_reshape
from src.histogram_matching import match_channel_to_histogram
from src.detail_preserve import detail_residual, apply_detail_preserve
from src.achromatic import build_achromatic_mask, apply_achromatic_anchor
from src.visualize import (
    ensure_dir, plot_scale_space, plot_regions, plot_histograms,
)


CHANNEL_NAMES = ("L", "a", "b")


# --------------------------------------------------------------------- #
#  單通道: 跨尺度漸進式重塑 (paper-correct)                              #
# --------------------------------------------------------------------- #
def _transfer_single_channel(src_chan: np.ndarray,
                             tgt_chan: np.ndarray,
                             value_range: Tuple[float, float],
                             cfg: TransferConfig,
                             channel_name: str,
                             save_prefix: str = "") -> Tuple[np.ndarray, Dict]:
    """
    對單一通道執行 paper 演算法:
        1) 建立 hs_raw, ht_raw.
        2) 從 k=1 (最粗) 到 k = ⌊perc·Smax⌋ 迭代:
                hs_k = smooth(目前累積 source, scale=k)
                ht_k = smooth(原始 target, scale=k)
                ho_k = progressive_reshape(hs_k, ht_k, k, Smax)
                目前累積 source ← ho_k
        3) 用最終 ho_final 對 src_chan 做 CDF 匹配 (Eq. 15).
    """
    B = cfg.B
    Smax = compute_smax(B, cfg.Bmin)

    # 論文: perc 控制「用了幾個尺度」, 不再做事後線性混合
    S_used = max(1, int(round(cfg.perc * Smax)))

    # --- 原始直方圖 ---
    hs_raw = channel_histogram(src_chan, B, value_range)
    ht_raw = channel_histogram(tgt_chan, B, value_range)

    # --- 跨尺度迭代 (paper Eq. 12 兩次轉移已封裝在 progressive_reshape) ---
    hs_current = hs_raw.copy()
    ho_per_scale = []
    regions_log = []
    for k in range(1, S_used + 1):
        hs_k = smooth_histogram_at_scale(hs_current, k, Smax)
        ht_k = smooth_histogram_at_scale(ht_raw,    k, Smax)

        ho_k = progressive_reshape(
            hs_k, ht_k, k, Smax,
            min_region_width=cfg.min_region_width,
            eps=cfg.eps,
        )
        hs_current = ho_k
        ho_per_scale.append(ho_k)
        regions_log.append({
            "k": k,
            "tgt_regions": detect_regions(ht_k, cfg.min_region_width),
            "src_regions_after_pass2": detect_regions(ho_k, cfg.min_region_width),
        })

    ho_final = hs_current

    # --- CDF 匹配 (Eq. 15) -- 注意 src_hist 用 raw, target hist 用 ho_final ---
    matched = match_channel_to_histogram(
        src_chan, hs_raw, ho_final, value_range
    )

    # --- 中間視覺化 ---
    if cfg.save_intermediate and save_prefix:
        ensure_dir(cfg.intermediate_dir)
        # 完整尺度金字塔 (raw 視圖)
        src_pyr = build_scale_space(hs_raw, Smax)
        tgt_pyr = build_scale_space(ht_raw, Smax)
        plot_scale_space(
            src_pyr,
            os.path.join(cfg.intermediate_dir,
                         f"{save_prefix}_src_scalespace_{channel_name}.png"),
            channel_name=f"src-{channel_name}",
        )
        plot_scale_space(
            tgt_pyr,
            os.path.join(cfg.intermediate_dir,
                         f"{save_prefix}_tgt_scalespace_{channel_name}.png"),
            channel_name=f"tgt-{channel_name}",
        )
        if regions_log:
            last = regions_log[-1]
            k_last = last["k"]
            plot_regions(
                tgt_pyr[k_last], last["tgt_regions"],
                os.path.join(cfg.intermediate_dir,
                             f"{save_prefix}_tgt_regions_{channel_name}.png"),
                title=f"Target regions (k={k_last}, {channel_name})",
            )
            plot_regions(
                ho_final, last["src_regions_after_pass2"],
                os.path.join(cfg.intermediate_dir,
                             f"{save_prefix}_ho_regions_{channel_name}.png"),
                title=f"h_o regions after pass2 (k={k_last}, {channel_name})",
            )
        plot_histograms(
            [hs_raw, ht_raw, ho_final],
            ["src raw", "tgt raw", f"h_o (S_used={S_used}/{Smax})"],
            os.path.join(cfg.intermediate_dir,
                         f"{save_prefix}_reshape_{channel_name}.png"),
            suptitle=f"Reshaped histogram - channel {channel_name}",
        )

    debug = {
        "Smax": Smax,
        "S_used": S_used,
        "ho_final": ho_final,
        "ho_per_scale": ho_per_scale,
        "regions_log": regions_log,
    }
    return matched, debug


# --------------------------------------------------------------------- #
#  全流程                                                               #
# --------------------------------------------------------------------- #
def progressive_color_transfer(src_rgb: np.ndarray,
                               tgt_rgb: np.ndarray,
                               cfg: TransferConfig,
                               save_prefix: str = "run") -> Tuple[np.ndarray, Dict]:
    """
    執行完整 paper-correct pipeline 並回傳 (output_rgb_uint8, debug_dict).
    """
    # ---- Lab 轉換 ----
    src_lab = rgb_to_lab(src_rgb)
    tgt_lab = rgb_to_lab(tgt_rgb)

    L_s, a_s, b_s = src_lab[..., 0], src_lab[..., 1], src_lab[..., 2]
    L_t, a_t, b_t = tgt_lab[..., 0], tgt_lab[..., 1], tgt_lab[..., 2]

    # ---- 通道別漸進式轉移 ----
    L_o, dbg_L = _transfer_single_channel(
        L_s, L_t, cfg.L_range, cfg, "L", save_prefix
    )
    a_o, dbg_a = _transfer_single_channel(
        a_s, a_t, cfg.a_range, cfg, "a", save_prefix
    )
    b_o, dbg_b = _transfer_single_channel(
        b_s, b_t, cfg.b_range, cfg, "b", save_prefix
    )

    # ---- 細節保留 (Eq. 16-17, 三通道分別處理) ----
    L_final = _detail_per_channel(L_s, L_o, cfg, cfg.L_range)
    a_final = _detail_per_channel(a_s, a_o, cfg, cfg.a_range)
    b_final = _detail_per_channel(b_s, b_o, cfg, cfg.b_range)

    # ---- 無彩色錨定 (Eq. 18, 位移補償版) ----
    achr_mask = build_achromatic_mask(
        a_s, b_s, wa=cfg.wa, gauss_sigma=cfg.achr_gauss_sigma
    )
    a_final, b_final = apply_achromatic_anchor(
        a_s, b_s, a_final, b_final, achr_mask
    )

    # ---- 組回 Lab -> RGB ----
    lab_final = np.stack([L_final, a_final, b_final], axis=-1)
    rgb_final = lab_to_rgb(lab_final)

    debug = {
        "Smax": dbg_L["Smax"],
        "S_used": dbg_L["S_used"],
        "L": dbg_L, "a": dbg_a, "b": dbg_b,
        "mask": achr_mask,
        "lab_final": lab_final,
    }
    return rgb_final, debug


# --------------------------------------------------------------------- #
#  Helpers                                                              #
# --------------------------------------------------------------------- #
def _detail_per_channel(chan_src: np.ndarray,
                        chan_out: np.ndarray,
                        cfg: TransferConfig,
                        value_range: Tuple[float, float]) -> np.ndarray:
    """單通道做 Eq. 16-17."""
    res_s = detail_residual(chan_src, cfg.bilat_d,
                            cfg.bilat_sigma_color, cfg.bilat_sigma_space)
    res_o = detail_residual(chan_out, cfg.bilat_d,
                            cfg.bilat_sigma_color, cfg.bilat_sigma_space)
    return apply_detail_preserve(chan_out, res_s, res_o,
                                 w_c=cfg.w_c, value_range=value_range)
