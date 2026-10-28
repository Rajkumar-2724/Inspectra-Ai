"""Heatmap post-processing, circle/ellipse defect localization, and annotation rendering."""
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np


class HeatmapProcessor:
    def normalize(self, hm: np.ndarray) -> np.ndarray:
        hm = np.nan_to_num(np.asarray(hm, dtype=np.float32), nan=0.0, posinf=1.0, neginf=0.0)
        return np.clip(hm, 0.0, 1.0)

    def resize(self, hm: np.ndarray, size_wh: tuple[int, int]) -> np.ndarray:
        return cv2.resize(hm, size_wh, interpolation=cv2.INTER_LINEAR)

    def smooth(self, hm: np.ndarray, sigma: float = 2.0) -> np.ndarray:
        return cv2.GaussianBlur(hm, (0, 0), sigma) if sigma > 0 else hm

    def colorize(self, hm: np.ndarray) -> np.ndarray:
        """Return RGB uint8 JET colour map of a 0..1 heatmap."""
        bgr = cv2.applyColorMap((np.clip(hm, 0, 1) * 255).astype(np.uint8), cv2.COLORMAP_JET)
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    def overlay(self, rgb: np.ndarray, hm: np.ndarray, alpha: float = 0.5) -> np.ndarray:
        color = self.colorize(hm)
        weight = (np.clip(hm, 0, 1) * alpha * 1.4)[..., None].clip(0, alpha)
        return (rgb.astype(np.float32) * (1 - weight) + color.astype(np.float32) * weight).astype(np.uint8)


@dataclass
class Region:
    x: int
    y: int
    w: int
    h: int
    area: int
    peak: float
    id: int = 1
    shape: str = "ellipse"  # "ellipse" | "circle"
    center: tuple[float, float] = (0.0, 0.0)  # (cx, cy) in processed image
    axes: tuple[float, float] = (0.0, 0.0)  # (semi_major / rx, semi_minor / ry)
    angle: float = 0.0  # rotation angle in degrees
    contour: list[list[int]] = field(default_factory=list)  # simplified polygon [x, y]
    original_box: tuple[int, int, int, int] | None = None  # (ox, oy, ow, oh)
    original_center: tuple[float, float] | None = None
    original_axes: tuple[float, float] | None = None
    label: str = "unclassified_anomaly"
    confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "w": self.w,
            "h": self.h,
            "area": self.area,
            "peak_score": round(self.peak, 4),
            "shape": self.shape,
            "center": [round(self.center[0], 2), round(self.center[1], 2)],
            "axes": [round(self.axes[0], 2), round(self.axes[1], 2)],
            "angle": round(self.angle, 2),
            "contour": self.contour,
            "original_box": list(self.original_box) if self.original_box else [self.x, self.y, self.w, self.h],
            "original_center": [round(self.original_center[0], 2), round(self.original_center[1], 2)] if self.original_center else [round(self.center[0], 2), round(self.center[1], 2)],
            "original_axes": [round(self.original_axes[0], 2), round(self.original_axes[1], 2)] if self.original_axes else [round(self.axes[0], 2), round(self.axes[1], 2)],
            "label": self.label,
            "confidence": round(self.confidence, 4) if self.confidence is not None else None,
        }


class DefectLocalizer:
    def __init__(self, min_area_frac: float = 0.00003, max_regions: int = 10, noise_kernel_size: int = 3):
        self.min_area_frac = min_area_frac
        self.max_regions = max_regions
        self.noise_kernel_size = noise_kernel_size

    def locate(self, hm: np.ndarray, threshold: float) -> list[Region]:
        """Convert anomaly map into connected regions with tight ellipse / circle fitting."""
        hm = np.nan_to_num(np.asarray(hm, dtype=np.float32), nan=0.0)
        mask = (hm >= threshold).astype(np.uint8)
        if mask.sum() == 0:
            return []

        # Conservative noise filtering: apply small morphological opening
        # to remove isolated single-pixel salt noise while preserving genuine tiny defects (e.g. 15px dots)
        if self.noise_kernel_size > 1 and mask.shape[0] >= 16 and mask.shape[1] >= 16:
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (self.noise_kernel_size, self.noise_kernel_size))
            filtered_mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            # If filtering removed everything, keep original mask if original had enough pixels
            if filtered_mask.sum() > 0 or mask.sum() < 4:
                mask = filtered_mask

        if mask.sum() == 0:
            return []

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        min_area = max(6, int(self.min_area_frac * hm.shape[0] * hm.shape[1]))
        candidate_regions: list[Region] = []

        for c in contours:
            area = int(cv2.contourArea(c))
            x, y, w, h = (int(v) for v in cv2.boundingRect(c))
            box_area = w * h
            # Allow regions if either contour area or bounding box area satisfies min_area
            if max(area, box_area) < min_area:
                continue

            peak = float(hm[y:y + h, x:x + w].max()) if w > 0 and h > 0 else 0.0

            # Derive tight circle or ellipse from contour geometry
            shape = "ellipse"
            center = (float(x + w / 2.0), float(y + h / 2.0))
            axes = (max(4.0, float(w / 2.0)), max(4.0, float(h / 2.0)))
            angle = 0.0

            if len(c) >= 5:
                try:
                    (fit_cx, fit_cy), (d1, d2), fit_angle = cv2.fitEllipse(c)
                    rx = max(4.0, (d1 / 2.0) * 1.12)
                    ry = max(4.0, (d2 / 2.0) * 1.12)
                    fit_cx = float(np.clip(fit_cx, x, x + w))
                    fit_cy = float(np.clip(fit_cy, y, y + h))
                    center = (fit_cx, fit_cy)
                    axes = (rx, ry)
                    angle = float(fit_angle)

                    # Prefer circle when aspect ratio is nearly uniform
                    ratio = max(rx, ry) / max(min(rx, ry), 1e-4)
                    if ratio < 1.25:
                        shape = "circle"
                        radius = (rx + ry) / 2.0
                        axes = (radius, radius)
                        angle = 0.0
                    else:
                        shape = "ellipse"
                except cv2.error:
                    (circle_cx, circle_cy), radius = cv2.minEnclosingCircle(c)
                    shape = "circle"
                    radius = max(4.0, radius * 1.12)
                    center = (float(circle_cx), float(circle_cy))
                    axes = (float(radius), float(radius))
                    angle = 0.0
            else:
                (circle_cx, circle_cy), radius = cv2.minEnclosingCircle(c)
                shape = "circle"
                radius = max(4.0, radius * 1.12)
                center = (float(circle_cx), float(circle_cy))
                axes = (float(radius), float(radius))
                angle = 0.0

            # Generate simplified contour points (for precise border rendering)
            epsilon = 0.02 * cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, max(1.0, epsilon), True)
            poly = [[int(pt[0][0]), int(pt[0][1])] for pt in approx[:32]]

            candidate_regions.append(
                Region(
                    x=x,
                    y=y,
                    w=w,
                    h=h,
                    area=max(area, box_area),
                    peak=peak,
                    shape=shape,
                    center=center,
                    axes=axes,
                    angle=angle,
                    contour=poly,
                )
            )

        candidate_regions.sort(key=lambda r: r.peak, reverse=True)
        selected = candidate_regions[: self.max_regions]
        for idx, r in enumerate(selected, start=1):
            r.id = idx
        return selected


def map_regions_to_original(regions: list[Region], scale: float, orig_wh: tuple[int, int]) -> list[Region]:
    """Map detected region coordinates back to the original acquisition image coordinates."""
    inv_scale = 1.0 / scale if scale > 0 else 1.0
    orig_w, orig_h = orig_wh
    for r in regions:
        ox = int(np.clip(round(r.x * inv_scale), 0, orig_w - 1))
        oy = int(np.clip(round(r.y * inv_scale), 0, orig_h - 1))
        ow = int(np.clip(round(r.w * inv_scale), 1, orig_w - ox))
        oh = int(np.clip(round(r.h * inv_scale), 1, orig_h - oy))
        r.original_box = (ox, oy, ow, oh)
        ocx = float(np.clip(r.center[0] * inv_scale, 0, orig_w - 1))
        ocy = float(np.clip(r.center[1] * inv_scale, 0, orig_h - 1))
        r.original_center = (ocx, ocy)
        orx = float(r.axes[0] * inv_scale)
        ory = float(r.axes[1] * inv_scale)
        r.original_axes = (orx, ory)
    return regions


def extract_region_crop(rgb: np.ndarray, region: Region | dict, pad_frac: float = 0.35, min_pad: int = 24, target_size: int = 160) -> np.ndarray:
    """Extract a zoomed contextual crop centered on the defect region."""
    h_img, w_img = rgb.shape[:2]
    if isinstance(region, Region):
        cx, cy = int(round(region.center[0])), int(round(region.center[1]))
        rw, rh = region.w, region.h
    else:
        center = region.get("center", [region.get("x", 0) + region.get("w", 20) / 2.0, region.get("y", 0) + region.get("h", 20) / 2.0])
        cx, cy = int(round(center[0])), int(round(center[1]))
        rw, rh = int(region.get("w", 20)), int(region.get("h", 20))
    half_w = max(min_pad, int(rw * (0.5 + pad_frac)))
    half_h = max(min_pad, int(rh * (0.5 + pad_frac)))
    pad = max(half_w, half_h)

    x0 = max(0, cx - pad)
    y0 = max(0, cy - pad)
    x1 = min(w_img, cx + pad)
    y1 = min(h_img, cy + pad)

    crop = rgb[y0:y1, x0:x1]
    if crop.size == 0 or crop.shape[0] < 2 or crop.shape[1] < 2:
        return np.zeros((target_size, target_size, 3), dtype=np.uint8)

    # Scale to standard thumbnail dimension while preserving detail
    interp = cv2.INTER_AREA if crop.shape[0] >= target_size else cv2.INTER_LINEAR
    return cv2.resize(crop, (target_size, target_size), interpolation=interp)


def draw_annotations(
    rgb: np.ndarray,
    regions: list[dict | Region],
    color: tuple[int, int, int] = (0, 229, 255),
    draw_ellipses: bool = True,
    draw_boxes: bool = False,
    draw_badges: bool = True,
) -> np.ndarray:
    """Draw tight ellipses / circles and numbered defect labels on the image."""
    out = rgb.copy()
    h_img, w_img = out.shape[:2]

    for idx, reg in enumerate(regions, start=1):
        if isinstance(reg, Region):
            d = reg.to_dict()
        else:
            d = reg

        reg_id = d.get("id", idx)
        shape = d.get("shape", "ellipse")
        center = d.get("center", [d["x"] + d["w"] / 2.0, d["y"] + d["h"] / 2.0])
        axes = d.get("axes", [d["w"] / 2.0, d["h"] / 2.0])
        angle = float(d.get("angle", 0.0))
        label = d.get("label", "unclassified_anomaly")
        conf = d.get("confidence")

        cx, cy = int(round(center[0])), int(round(center[1]))
        rx, ry = max(4, int(round(axes[0]))), max(4, int(round(axes[1])))

        # 1. Draw tight circle or ellipse outline
        if draw_ellipses:
            if shape == "circle" or abs(rx - ry) < 2:
                radius = max(rx, ry)
                cv2.circle(out, (cx, cy), radius, color, 2, cv2.LINE_AA)
            else:
                cv2.ellipse(out, (cx, cy), (rx, ry), angle, 0, 360, color, 2, cv2.LINE_AA)

        # 2. Draw bounding box if explicitly requested
        if draw_boxes:
            bx, by, bw, bh = d["x"], d["y"], d["w"], d["h"]
            cv2.rectangle(out, (bx, by), (bx + bw, by + bh), (color[0] // 2, color[1] // 2, color[2] // 2), 1, cv2.LINE_AA)

        # 3. Draw numbered badge & defect label
        if draw_badges:
            display_label = "Unclassified anomaly" if label == "unclassified_anomaly" else label.replace("_", " ").title()
            if conf is not None:
                display_label += f" {conf * 100:.0f}%"
            badge_text = f"#{reg_id} {display_label}"

            font = cv2.FONT_HERSHEY_SIMPLEX
            scale = 0.42
            thick = 1
            (tw, th), base = cv2.getTextSize(badge_text, font, scale, thick)

            # Position label pill right above the top boundary of the region
            top_y = cy - ry
            py = max(th + 6, min(top_y - 6, h_img - 6))
            px = max(4, min(cx - tw // 2, w_img - tw - 8))

            # Pill background & crisp outline
            cv2.rectangle(out, (px - 3, py - th - 3), (px + tw + 4, py + 3), (11, 19, 36), -1)
            cv2.rectangle(out, (px - 3, py - th - 3), (px + tw + 4, py + 3), color, 1, cv2.LINE_AA)
            cv2.putText(out, badge_text, (px, py), font, scale, (255, 255, 255), thick, cv2.LINE_AA)

    return out


def draw_boxes(rgb: np.ndarray, boxes: list[dict], color=(0, 229, 255)) -> np.ndarray:
    """Backward-compatible drawing function that renders tight ellipses/circles with badges."""
    return draw_annotations(rgb, boxes, color=color, draw_ellipses=True, draw_boxes=False, draw_badges=True)
