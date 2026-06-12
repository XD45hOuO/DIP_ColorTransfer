"""
color_space.py
--------------
RGB <-> CIELab 轉換 (假設 D65 白點)。

採用 OpenCV 的 cvtColor 進行轉換，但其 Lab 範圍為:
    L: [0, 255]  (= L* * 255/100)
    a: [0, 255]  (= a* + 128)
    b: [0, 255]  (= b* + 128)

為了與論文中的 CIELab 區段 (L*∈[0,100], a*,b*∈[-128,127]) 一致,
我們在這裡額外做線性還原, 對外回傳「論文尺度」的浮點 Lab。
"""

from __future__ import annotations

import os

import cv2
import numpy as np


# 支援的副檔名 (小寫, 含點)
SUPPORTED_EXTS = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")


def rgb_to_lab(img_rgb: np.ndarray) -> np.ndarray:
    """
    將 uint8 RGB 影像轉換為論文尺度的 float32 CIELab。

    Args:
        img_rgb: H x W x 3, dtype=uint8, RGB 順序。

    Returns:
        H x W x 3, dtype=float32, 通道順序為 (L*, a*, b*).
    """
    if img_rgb.dtype != np.uint8:
        # OpenCV 的 D65 Lab 公式要求 uint8 / float32(0~1)
        img_rgb = np.clip(img_rgb, 0, 255).astype(np.uint8)

    # OpenCV 使用 BGR, 故先轉一次
    img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
    lab_cv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)

    # OpenCV Lab -> 論文 Lab
    L = lab_cv[..., 0] * (100.0 / 255.0)
    a = lab_cv[..., 1] - 128.0
    b = lab_cv[..., 2] - 128.0
    return np.stack([L, a, b], axis=-1)


def lab_to_rgb(img_lab: np.ndarray) -> np.ndarray:
    """
    將論文尺度 Lab 還原為 uint8 RGB。

    Args:
        img_lab: H x W x 3, float, 論文尺度 (L:0~100, a/b:-128~127).

    Returns:
        H x W x 3, dtype=uint8, RGB.
    """
    L = np.clip(img_lab[..., 0], 0.0, 100.0) * (255.0 / 100.0)
    a = np.clip(img_lab[..., 1], -128.0, 127.0) + 128.0
    b = np.clip(img_lab[..., 2], -128.0, 127.0) + 128.0
    lab_cv = np.stack([L, a, b], axis=-1).astype(np.uint8)

    bgr = cv2.cvtColor(lab_cv, cv2.COLOR_LAB2BGR)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return rgb


def _ensure_uint8(img: np.ndarray) -> np.ndarray:
    """
    將不同深度的影像歸一化到 uint8:
        uint16        -> 線性除以 257 (= 65535/255)
        float (0~1)   -> 乘以 255
        float (>1)    -> 視為已是 0~255 範圍, 直接 clip
    """
    if img.dtype == np.uint8:
        return img
    if img.dtype == np.uint16:
        return (img / 257.0).round().clip(0, 255).astype(np.uint8)
    if np.issubdtype(img.dtype, np.floating):
        m = float(img.max()) if img.size else 1.0
        if m <= 1.0 + 1e-6:
            return (img * 255.0).round().clip(0, 255).astype(np.uint8)
        return img.round().clip(0, 255).astype(np.uint8)
    # 其它整數型別 (int16/int32)
    return img.clip(0, 255).astype(np.uint8)


def load_image_rgb(path: str) -> np.ndarray:
    """
    讀取影像並回傳 RGB uint8, 支援 .png/.jpg/.jpeg/.tif/.tiff/.bmp。

    處理細節:
        - 自動處理 alpha 通道 (RGBA -> 丟棄 A)
        - 自動處理 16-bit / float TIFF (降深度至 uint8)
        - 灰階輸入會擴展為 3 通道
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"檔案不存在: {path}")

    ext = os.path.splitext(path)[1].lower()
    if ext not in SUPPORTED_EXTS:
        raise ValueError(
            f"不支援的影像格式 {ext!r}; 目前支援: {', '.join(SUPPORTED_EXTS)}"
        )

    raw = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if raw is None:
        raise IOError(f"無法解碼影像 (檔案可能損毀或編碼不被 OpenCV 支援): {path}")

    # 1) 通道處理 (OpenCV 回傳 BGR / BGRA / 單通道)
    if raw.ndim == 2:                       # 灰階
        bgr = cv2.cvtColor(raw, cv2.COLOR_GRAY2BGR)
    elif raw.shape[2] == 4:                 # BGRA -> BGR
        bgr = cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)
    elif raw.shape[2] == 3:
        bgr = raw
    else:
        raise ValueError(f"未預期的通道數 {raw.shape[2]} ({path})")

    # 2) 位元深度歸一化
    bgr = _ensure_uint8(bgr)

    # 3) BGR -> RGB
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def resize_to_fit(img_rgb: np.ndarray,
                  max_w: int = 1920,
                  max_h: int = 1080,
                  keep_aspect: bool = True) -> np.ndarray:
    """
    將影像縮放至 max_w x max_h 之內以加速後續處理。

    Args:
        img_rgb:    H x W x 3 uint8.
        max_w/max_h: 上限寬高 (預設 1920x1080).
        keep_aspect: True = 等比例縮放 (長邊貼合, 不變形);
                     False = 直接拉伸至 max_w x max_h.

    Returns:
        縮放後 RGB uint8. 若原圖已小於上限則原樣回傳。
    """
    h, w = img_rgb.shape[:2]
    if keep_aspect:
        scale = min(max_w / w, max_h / h, 1.0)
        if scale >= 1.0:
            return img_rgb
        new_w, new_h = int(round(w * scale)), int(round(h * scale))
    else:
        if (w, h) == (max_w, max_h):
            return img_rgb
        new_w, new_h = max_w, max_h

    interp = cv2.INTER_AREA if new_w * new_h < w * h else cv2.INTER_CUBIC
    return cv2.resize(img_rgb, (new_w, new_h), interpolation=interp)


def save_image_rgb(path: str, img_rgb: np.ndarray) -> None:
    """
    儲存 RGB uint8 影像; 副檔名決定編碼器:
        .png        無損壓縮
        .jpg/.jpeg  有損, quality=95
        .tif/.tiff  無損 (預設 LZW)
        .bmp        無壓縮
    """
    ext = os.path.splitext(path)[1].lower()
    if ext not in SUPPORTED_EXTS:
        raise ValueError(
            f"不支援的輸出格式 {ext!r}; 目前支援: {', '.join(SUPPORTED_EXTS)}"
        )

    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    if img_rgb.dtype != np.uint8:
        img_rgb = _ensure_uint8(img_rgb)
    bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)

    params = []
    if ext in (".jpg", ".jpeg"):
        params = [cv2.IMWRITE_JPEG_QUALITY, 95]
    elif ext == ".png":
        params = [cv2.IMWRITE_PNG_COMPRESSION, 3]

    ok = cv2.imwrite(path, bgr, params)
    if not ok:
        raise IOError(f"寫入影像失敗: {path}")
