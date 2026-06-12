"""
main.py
-------
CLI 入口程式。

範例:
    python main.py --source images/source/a.png ^
                   --target images/target/b.png ^
                   --perc 0.8 ^
                   --output results/final/out.png
"""

from __future__ import annotations

import argparse
import os
import sys

from config import TransferConfig, DEFAULT_CONFIG
from src.color_space import load_image_rgb, save_image_rgb, resize_to_fit
from src.transfer import progressive_color_transfer
from src.visualize import (
    plot_triplet, ensure_dir,
    plot_rgb_histograms_triplet, plot_rgb_histogram_single,
)
from src.stats import print_stats_comparison
from src.improved_color_transfer import improved_color_transfer


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Progressive Color Transfer (DIP Term Project)"
    )
    p.add_argument("--source", "-s", required=True,
                   help="Source 影像路徑 (待轉色)")
    p.add_argument("--target", "-t", required=True,
                   help="Target 影像路徑 (色調參考)")
    p.add_argument("--output", "-o", default="results/final/output.png",
                   help="輸出影像路徑")
    p.add_argument("--perc", type=float, default=DEFAULT_CONFIG.perc,
                   help="轉移百分比 (0~1), 0=不轉, 1=完整轉移")
    p.add_argument("--B", type=int, default=DEFAULT_CONFIG.B,
                   help="直方圖 bin 數量 (預設 400)")
    p.add_argument("--Bmin", type=int, default=DEFAULT_CONFIG.Bmin,
                   help="最小 bin 數量, 控制最大尺度 (預設 10)")
    p.add_argument("--wa", type=float, default=DEFAULT_CONFIG.wa,
                   help="無彩色閾值比例 (預設 0.08)")
    p.add_argument("--wc", type=float, default=DEFAULT_CONFIG.w_c,
                   help="細節保留權重 (預設 1.0)")
    p.add_argument("--no-intermediate", action="store_true",
                   help="不輸出中間步驟圖")
    p.add_argument("--prefix", default="run",
                   help="中間檔案前綴 (有助多次實驗區分)")
    p.add_argument("--resize", default="1920x1080",
                   help="自動將輸入影像縮放至此上限 (WxH), 預設 1920x1080. "
                        "傳入 'none' 可關閉.")
    p.add_argument("--stretch", action="store_true",
                   help="關閉等比例縮放, 直接拉伸到 --resize 指定的尺寸 "
                        "(預設保留長寬比).")
    p.add_argument("--no-rgb-hist", action="store_true",
                   help="不輸出 RGB 直方圖 (預設會輸出 src/tgt/out 三聯與單張)")
    p.add_argument("--rgb-hist-bins", type=int, default=256,
                   help="RGB 直方圖 bin 數 (預設 256)")
    p.add_argument("--no-stats", action="store_true",
                   help="不在終端列印 RGB / Lab 統計表")
    p.add_argument("--method", choices=("paper", "improved"), default="paper",
                   help="paper = 純論文方法; improved = saliency-weighted 改良方法")
    p.add_argument("--alpha-salient", type=float, default=0.5,
                   help="(改良方法) 主體區域轉移強度 (預設 0.5 = 保留 50%% 原色)")
    p.add_argument("--alpha-background", type=float, default=1.0,
                   help="(改良方法) 背景區域轉移強度 (預設 1.0 = 完全採用 target)")
    p.add_argument("--saliency-size", type=int, default=64,
                   help="(改良方法) saliency 計算尺寸 (預設 64px)")
    return p.parse_args()


def _parse_resize(spec: str):
    """解析 '1920x1080' 字串; 'none' 表示停用."""
    if spec is None or spec.lower() in ("none", "off", "0"):
        return None
    try:
        w, h = spec.lower().split("x")
        return int(w), int(h)
    except Exception as e:
        raise ValueError(f"--resize 格式錯誤: {spec!r}, 應為 'WxH' 例如 '1920x1080'") from e


def main() -> int:
    args = parse_args()

    cfg = TransferConfig(
        B=args.B,
        Bmin=args.Bmin,
        perc=args.perc,
        wa=args.wa,
        w_c=args.wc,
        save_intermediate=not args.no_intermediate,
    )

    print(f"[INFO] Loading source: {args.source}")
    src = load_image_rgb(args.source)
    print(f"[INFO] Loading target: {args.target}")
    tgt = load_image_rgb(args.target)
    print(f"[INFO] Source shape (raw)={src.shape}, Target shape (raw)={tgt.shape}")

    resize_spec = _parse_resize(args.resize)
    if resize_spec is not None:
        max_w, max_h = resize_spec
        keep_aspect = not args.stretch
        src = resize_to_fit(src, max_w, max_h, keep_aspect=keep_aspect)
        tgt = resize_to_fit(tgt, max_w, max_h, keep_aspect=keep_aspect)
        mode = "stretch" if args.stretch else "fit"
        print(f"[INFO] Resized to <= {max_w}x{max_h} ({mode}); "
              f"src={src.shape}, tgt={tgt.shape}")
    else:
        print("[INFO] Auto-resize disabled.")
    print(f"[INFO] perc={cfg.perc}, B={cfg.B}, Bmin={cfg.Bmin}, "
          f"wa={cfg.wa}, wc={cfg.w_c}")

    if args.method == "improved":
        print(f"[INFO] Running IMPROVED (saliency-weighted) transfer  "
              f"(α_salient={args.alpha_salient}, α_bg={args.alpha_background})")
        out, debug = improved_color_transfer(
            src, tgt, cfg,
            alpha_salient=args.alpha_salient,
            alpha_background=args.alpha_background,
            saliency_size=args.saliency_size,
            save_prefix=args.prefix,
        )
        # 把底層論文 debug 對齊以共用後續流程
        debug["Smax"]   = debug["paper_debug"]["Smax"]
        debug["S_used"] = debug["paper_debug"]["S_used"]
    else:
        print("[INFO] Running paper-standard progressive color transfer...")
        out, debug = progressive_color_transfer(src, tgt, cfg,
                                                save_prefix=args.prefix)

    # ---- 終端顯示 RGB / CIELab 統計 ----
    if not args.no_stats:
        print_stats_comparison([
            ("Source", src),
            ("Target", tgt),
            ("Output", out),
        ])
    print(f"[INFO] Smax = {debug['Smax']}, S_used = {debug['S_used']} "
          f"(perc={cfg.perc} -> {debug['S_used']}/{debug['Smax']} 個尺度)")

    # ---- 儲存輸出 ----
    ensure_dir(os.path.dirname(args.output) or ".")
    save_image_rgb(args.output, out)
    print(f"[OK] Output saved -> {args.output}")

    # ---- 三聯比較圖 ----
    ensure_dir(cfg.final_dir)
    triplet_path = os.path.join(cfg.final_dir, f"{args.prefix}_triplet.png")
    plot_triplet(src, tgt, out, triplet_path,
                 suptitle=f"Progressive Color Transfer  (perc={cfg.perc})")
    print(f"[OK] Comparison plot saved -> {triplet_path}")

    # ---- RGB 直方圖 (放在 intermediate 資料夾) ----
    if not args.no_rgb_hist:
        ensure_dir(cfg.intermediate_dir)
        bins = args.rgb_hist_bins
        rgb_triplet_path = os.path.join(
            cfg.intermediate_dir, f"{args.prefix}_rgb_hist.png"
        )
        plot_rgb_histograms_triplet(
            src, tgt, out, rgb_triplet_path,
            bins=bins,
            suptitle=f"RGB histograms  (perc={cfg.perc}, bins={bins})",
        )
        print(f"[OK] RGB histograms saved -> {rgb_triplet_path}")

        # 三張獨立的單圖, 方便放入報告
        for name, img in (("src", src), ("tgt", tgt), ("out", out)):
            single_path = os.path.join(
                cfg.intermediate_dir, f"{args.prefix}_rgb_hist_{name}.png"
            )
            plot_rgb_histogram_single(
                img, single_path, bins=bins,
                title=f"{name.upper()} RGB histogram",
            )
        print(f"[OK] Per-image RGB histograms saved -> "
              f"{cfg.intermediate_dir}/{args.prefix}_rgb_hist_(src|tgt|out).png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
