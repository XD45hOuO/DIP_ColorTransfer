"""
stats.py
--------
計算並以終端表格顯示影像的 RGB / CIELab 通道統計值。
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np

from src.color_space import rgb_to_lab


# 顯示欄位順序
_COL_KEYS = ("min", "max", "mean", "std", "median")


def _channel_stats(arr: np.ndarray) -> Dict[str, float]:
    """單通道的 5 個基本統計量."""
    flat = arr.reshape(-1).astype(np.float64)
    return {
        "min":    float(np.min(flat)),
        "max":    float(np.max(flat)),
        "mean":   float(np.mean(flat)),
        "std":    float(np.std(flat)),
        "median": float(np.median(flat)),
    }


def compute_image_stats(img_rgb: np.ndarray
                        ) -> Tuple[Dict[str, Dict[str, float]],
                                   Dict[str, Dict[str, float]]]:
    """
    計算 RGB 與 CIELab 各通道的統計值。

    Returns:
        (rgb_stats, lab_stats), 每個是 {channel_name: {stat_key: value}}.
    """
    rgb_stats = {
        "R": _channel_stats(img_rgb[..., 0]),
        "G": _channel_stats(img_rgb[..., 1]),
        "B": _channel_stats(img_rgb[..., 2]),
    }
    lab = rgb_to_lab(img_rgb)
    lab_stats = {
        "L*": _channel_stats(lab[..., 0]),
        "a*": _channel_stats(lab[..., 1]),
        "b*": _channel_stats(lab[..., 2]),
    }
    return rgb_stats, lab_stats


def _format_table(stats: Dict[str, Dict[str, float]],
                  space_name: str) -> str:
    """把 stats dict 格式化為對齊的表格字串."""
    header = f"  {space_name:<5} | " + " | ".join(f"{k:>8}" for k in _COL_KEYS)
    sep = "  " + "-" * (len(header) - 2)
    lines = [header, sep]
    for ch, vals in stats.items():
        cells = " | ".join(f"{vals[k]:>8.3f}" for k in _COL_KEYS)
        lines.append(f"  {ch:<5} | {cells}")
    return "\n".join(lines)


def print_image_stats(img_rgb: np.ndarray,
                      label: str = "image") -> None:
    """印出單張影像的 RGB + Lab 統計表."""
    rgb_stats, lab_stats = compute_image_stats(img_rgb)
    print(f"\n[STATS] {label}  shape={img_rgb.shape}")
    print(_format_table(rgb_stats, "RGB"))
    print(_format_table(lab_stats, "Lab"))


def print_stats_comparison(images: List[Tuple[str, np.ndarray]]) -> None:
    """
    對一組 [(label, img_rgb), ...] 各印一份 RGB+Lab 統計表。
    """
    print("\n" + "=" * 62)
    print(" Image channel statistics  (RGB: 0-255, L*: 0-100, a*/b*: -128~127)")
    print("=" * 62)
    for label, img in images:
        print_image_stats(img, label=label)
    print("=" * 62 + "\n")
