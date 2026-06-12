"""
visualize.py
------------
中間步驟與最終結果的視覺化, 方便寫入期末報告。
"""

from __future__ import annotations

import os
from typing import List, Tuple

import matplotlib
matplotlib.use("Agg")  # 無視窗環境也能存圖
import matplotlib.pyplot as plt
import numpy as np


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def plot_histograms(hist_list: List[np.ndarray],
                    titles: List[str],
                    save_path: str,
                    suptitle: str = "") -> None:
    """將多個直方圖畫在同一張圖內 (橫向 subplot)."""
    n = len(hist_list)
    fig, axes = plt.subplots(1, n, figsize=(4 * n, 3))
    if n == 1:
        axes = [axes]
    for ax, h, t in zip(axes, hist_list, titles):
        ax.bar(np.arange(h.shape[0]), h, width=1.0)
        ax.set_title(t)
        ax.set_xlabel("bin")
        ax.set_ylabel("prob")
    if suptitle:
        fig.suptitle(suptitle)
    fig.tight_layout()
    fig.savefig(save_path, dpi=120)
    plt.close(fig)


def plot_scale_space(pyramid: List[np.ndarray],
                     save_path: str,
                     channel_name: str = "L") -> None:
    """畫出尺度空間金字塔 (k=0..Smax)."""
    titles = [f"{channel_name}  k={k}" for k in range(len(pyramid))]
    plot_histograms(pyramid, titles, save_path,
                    suptitle=f"Scale-space histogram ({channel_name})")


def plot_regions(hist: np.ndarray,
                 regions: List[Tuple[int, int]],
                 save_path: str,
                 title: str = "") -> None:
    """畫出直方圖及其切分區段 (用紅線標記邊界)."""
    fig, ax = plt.subplots(1, 1, figsize=(6, 3))
    ax.bar(np.arange(hist.shape[0]), hist, width=1.0)
    for (s, e) in regions:
        ax.axvline(s, color="red", linewidth=0.6, linestyle="--")
        ax.axvline(e, color="red", linewidth=0.6, linestyle="--")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(save_path, dpi=120)
    plt.close(fig)


def plot_rgb_histogram(img_rgb: np.ndarray,
                       ax,
                       title: str = "",
                       bins: int = 256) -> None:
    """
    在指定的 matplotlib axes 上繪製單張影像的 R/G/B 三通道直方圖 (overlay).
    """
    colors = ("red", "green", "blue")
    for c, color in enumerate(colors):
        hist, edges = np.histogram(img_rgb[..., c], bins=bins, range=(0, 256))
        centers = 0.5 * (edges[:-1] + edges[1:])
        ax.plot(centers, hist, color=color, linewidth=1.0,
                alpha=0.85, label=color.upper())
        ax.fill_between(centers, hist, alpha=0.15, color=color)
    ax.set_xlim(0, 255)
    ax.set_xlabel("intensity")
    ax.set_ylabel("count")
    ax.set_title(title)
    ax.legend(loc="upper right", fontsize=8)


def plot_rgb_histograms_triplet(src_rgb: np.ndarray,
                                tgt_rgb: np.ndarray,
                                out_rgb: np.ndarray,
                                save_path: str,
                                bins: int = 256,
                                suptitle: str = "RGB histograms") -> None:
    """source / target / output 三張影像的 RGB 直方圖並排輸出."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    plot_rgb_histogram(src_rgb, axes[0], "Source", bins=bins)
    plot_rgb_histogram(tgt_rgb, axes[1], "Target", bins=bins)
    plot_rgb_histogram(out_rgb, axes[2], "Output", bins=bins)
    fig.suptitle(suptitle)
    fig.tight_layout()
    fig.savefig(save_path, dpi=130)
    plt.close(fig)


def plot_rgb_histogram_single(img_rgb: np.ndarray,
                              save_path: str,
                              bins: int = 256,
                              title: str = "RGB histogram") -> None:
    """單張影像的 RGB 直方圖 (獨立檔案)."""
    fig, ax = plt.subplots(1, 1, figsize=(6, 4))
    plot_rgb_histogram(img_rgb, ax, title, bins=bins)
    fig.tight_layout()
    fig.savefig(save_path, dpi=130)
    plt.close(fig)


def plot_triplet(src_rgb: np.ndarray,
                 tgt_rgb: np.ndarray,
                 out_rgb: np.ndarray,
                 save_path: str,
                 suptitle: str = "Progressive Color Transfer") -> None:
    """source / target / output 三聯圖."""
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    for ax, img, t in zip(axes,
                          [src_rgb, tgt_rgb, out_rgb],
                          ["Source", "Target", "Output"]):
        ax.imshow(img)
        ax.set_title(t)
        ax.axis("off")
    fig.suptitle(suptitle)
    fig.tight_layout()
    fig.savefig(save_path, dpi=140)
    plt.close(fig)
