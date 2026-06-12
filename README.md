# Progressive Color Transfer for Images of Arbitrary Dynamic Range

> DIP 期末專案：實作論文 *Progressive color transfer for images of arbitrary dynamic range* 的核心演算法。
> 在 CIELab 空間中，透過尺度空間直方圖 + 區段漸進式重塑 + 雙邊濾波細節保留 + 無彩色錨定，將一張影像的色調漸進地轉移到另一張影像。

---

## 1. 專案結構

```
DIP_Term/
├── README.md
├── requirements.txt
├── main.py                 # CLI 入口
├── config.py               # 全域預設參數
├── src/
│   ├── color_space.py        # RGB <-> CIELab (D65)
│   ├── scale_space.py        # 尺度空間直方圖 (bicubic↓ + nearest↑)
│   ├── feature_detection.py  # 一階/二階導數 minima 偵測 → 區段切分
│   ├── reshaping.py          # 漸進式 μ,σ 區段重塑 + 兩次轉移
│   ├── histogram_matching.py # CDF 對齊
│   ├── detail_preserve.py    # 雙邊濾波器 + 細節殘差控制
│   ├── achromatic.py         # 無彩色遮罩 + Gaussian 平滑
│   ├── transfer.py           # 串接整個 pipeline
│   └── visualize.py          # 中間步驟 + 三聯比較圖
├── images/
│   ├── source/             # 放待轉色影像
│   └── target/             # 放色調參考影像
└── results/
    ├── intermediate/       # 每尺度/每通道直方圖、區段、重塑圖
    └── final/              # 最終結果與三聯比較圖
```

---

## 2. 環境安裝

建議使用 Python 3.10+，並建立虛擬環境：

```powershell
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

需要的核心套件：

| 套件 | 用途 |
| --- | --- |
| numpy / scipy | 數值運算 |
| opencv-python | 色彩空間轉換、雙邊濾波、影像 I/O |
| matplotlib | 直方圖與比較圖視覺化 |
| Pillow | 部分影像格式相容性 |

---

## 3. 執行方式

最小可執行命令：

```powershell
python main.py --source path/to/your/source.jpg `
               --target path/to/your/target.jpg `
               --output path/to/your/output.jpg `
               --perc 1.0
```

完整參數：

| 參數 | 預設 | 說明 |
| --- | --- | --- |
| `--source / -s` | (必填) | Source 影像 (待轉色) |
| `--target / -t` | (必填) | Target 影像 (色調參考) |
| `--output / -o` | `results/final/output.png` | 輸出檔路徑 |
| `--perc` | `1.0` | **使用尺度比例** (0~1)：實際使用尺度數 `S_used = round(perc·Smax)`，越小代表只匹配越粗的特徵 (對應論文 Fig. 5 的 `s = 0.25/0.50/1.00 Smax`) |
| `--B` | `400` | 直方圖 bin 數量 |
| `--Bmin` | `10` | 最小 bin 數量 (控制最大尺度 `Smax = ⌊log₂(B/Bmin)⌋`) |
| `--wa` | `0.08` | 無彩色遮罩閾值比例 |
| `--wc` | `1.0` | 細節殘差混合權重 |
| `--no-intermediate` | off | 不輸出中間步驟圖 (加速、節省硬碟) |
| `--prefix` | `run` | 中間檔案前綴 (多次實驗區分用) |
| `--resize` | `1920x1080` | 自動將輸入縮放至此上限 (`WxH`)。傳 `none` 可關閉 |
| `--stretch` | off | 直接拉伸到 `--resize` 尺寸 (預設等比例縮放, 不變形) |

執行後會在以下位置產生檔案：

- `results/final/output.png` — 最終輸出
- `results/final/<prefix>_triplet.png` — Source / Target / Output 三聯比較圖
- `results/intermediate/<prefix>_*` — 每一通道 (L, a, b) 的尺度空間、區段切分、重塑直方圖

---

## 3.1 支援的影像格式

輸入 / 輸出皆支援:

| 副檔名 | 輸入 | 輸出 |
| --- | --- | --- |
| `.png` | 自動丟棄 alpha 通道 | 無損 (壓縮 lv.3) |
| `.jpg` / `.jpeg` | 一般 8-bit | quality=95 |
| `.tif` / `.tiff` | 自動降 16-bit→8-bit, 丟棄 alpha | 無損 (LZW) |
| `.bmp` | 一般 8-bit | 無壓縮 |

混搭沒問題，例如 `--source a.tif --target b.png --output out.jpg`。

---

## 4. 演算法流程對應論文

| 論文步驟 | 對應檔案 / 函式 |
| --- | --- |
| RGB → CIELab (D65)，分通道處理 | `src/color_space.py` :: `rgb_to_lab` |
| 尺度空間直方圖 (`Smax = ⌊log₂(B/Bmin)⌋`)，bicubic↓ + nearest↑ | `src/scale_space.py` :: `build_scale_space`, `smooth_histogram_at_scale` |
| 一階/二階導數求 minima → 區段 | `src/feature_detection.py` :: `find_minima`, `detect_regions` |
| 漸進式區段重塑 Eq. (12)，分母 `w_s·σ_s`；兩次轉移 (target regions → 更新後 source regions) | `src/reshaping.py` :: `progressive_reshape` |
| 累積直方圖 CDF 匹配 | `src/histogram_matching.py` :: `match_channel_to_histogram` |
| 雙邊濾波分離細節 (L/a/b 三通道分別)：`I_o' = I_o + w_c (I_res,s − I_res,o)` Eq. (16-17) | `src/detail_preserve.py` :: `detail_residual`, `apply_detail_preserve` |
| 無彩色錨定 (Eq. 18)，位移補償版：`a_final = a_out − mask · (a_out−a_src)` | `src/achromatic.py` :: `build_achromatic_mask`, `apply_achromatic_anchor` |
| 整體 pipeline | `src/transfer.py` :: `progressive_color_transfer` |

---

## 5. 參數調整建議

- **色調轉得太重 / 顏色失真**：把 `--perc` 從 1.0 降到 0.5 ~ 0.8。
- **白色或灰色區域出現染色**：把 `--wa` 從 0.08 提高到 0.12 ~ 0.15。
- **細節 (邊緣、紋理) 過度模糊**：把 `--wc` 從 1.0 提升到 1.2 ~ 1.5。
- **直方圖偵測太破碎 (區段太多)**：把 `--B` 降到 256 或將 `config.min_region_width` 提高。
- **大圖很慢**：先 `cv2.resize` 影像到 1024px 寬度再執行，幾乎不影響色彩轉移效果 (色彩統計對解析度不敏感)。

---

## 6. 期末報告建議放入的圖

`results/intermediate/<prefix>_*` 已自動包含：

1. **Scale-space 金字塔** — 三通道分別呈現 `k = 0..Smax` 的平滑結果，
   可說明高頻細節隨尺度遞減。
2. **Region 切分圖** — 紅色虛線標出 minima，
   說明區段是如何被偵測出來的。
3. **重塑前後直方圖** — `src raw / tgt raw / reshaped (ho)`
   一字排開，可直觀說明色調已對齊到 target 的分布。

最終 `<prefix>_triplet.png` 可作為主視覺 (Source / Target / Output)。

---

## 6.5 改良方法：Saliency-Weighted Transfer

論文方法用單一全域 `perc` 控制整張影像，無法區分「主體」與「背景」。
本專案在論文之上新增 [src/improved_color_transfer.py](src/improved_color_transfer.py)，加入自動顯著性偵測：

| 區域 | 顯著性 S(p) | 預設 α(p) | 行為 |
|---|---|---|---|
| 主體（人臉、物體） | ~1 | 0.5 (`--alpha-salient`) | 保留 50% 原色，避免主體被過度染色 |
| 背景 | ~0 | 1.0 (`--alpha-background`) | 完全採用 target 色調 |

**演算法步驟：**
1. 跑論文標準 pipeline → `paper_out`
2. 用 Hou & Zhang (2007) **Spectral Residual**（純 FFT，無需訓練模型）算出 saliency map S(p)
3. `α(p) = α_bg + (α_salient − α_bg) · S(p)`
4. **CIELab 空間**做 per-pixel 漸進混合：`out_Lab = (1−α)·src_Lab + α·paper_Lab`

**執行：**
```powershell
python main.py -s images/source/007.jpg -t images/target/009.jpg `
               -o results/final/improved.png --method improved `
               --alpha-salient 0.5 --alpha-background 1.0
```

執行後 `results/intermediate/<prefix>_*` 額外產生：

- `<prefix>_saliency.png` — Source + Spectral Residual saliency 並排
- `<prefix>_alpha.png` — per-pixel 轉移強度地圖（viridis colormap）
- `<prefix>_4panel.png` — `Source / Target / Paper / Improved` 四格 ablation

**與論文 Section 4 (Region Selection) 的關係：**
論文用 Soft Scissors 手繪 matte 達成類似分區控制；本方法將 matte 自動化，
等同於補上論文「需要使用者輸入」的限制。

---

## 7. 已知限制

- 區段對應採「依序 1-1 配對」，當 source 與 target 的色彩分布結構差異極大時 (例如 source 全暗、target 全亮)，可能出現非預期的區段配對。可在 `src/reshaping.py :: match_regions` 改成「以 μ 距離匹配」做進一步實驗。
- 程式預期輸入為 8-bit RGB；若要處理 HDR / 16-bit 影像，需額外擴充 `color_space.py` 的數值範圍處理。
- 雙邊濾波目前只作用於 L 通道，符合論文中「細節主要存於亮度通道」的假設。

---

## 8. 學術引用

> Hwang, Y., Lee, J. Y., Kweon, I. S., & Kim, S. J. (2014).
> *Color transfer using probabilistic moving least squares.*  
> 以及 paper 資料夾中提供之 *Progressive color transfer for images of arbitrary dynamic range*。

僅供 NCHU DIP 課程學術用途。
