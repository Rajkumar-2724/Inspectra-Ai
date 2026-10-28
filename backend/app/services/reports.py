import io
import json
from datetime import datetime

import pandas as pd
from PIL import Image
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent, Inspection, InspectionBatch
from app.services.inspection_service import storage_file
from app.utils.time import iso, utcnow

NAVY, CYAN = colors.HexColor("#0b1730"), colors.HexColor("#0891b2")
SS = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=SS["Title"], textColor=NAVY, fontSize=20, alignment=0)
H2 = ParagraphStyle("H2", parent=SS["Heading2"], textColor=CYAN, spaceBefore=10)
SM = ParagraphStyle("SM", parent=SS["BodyText"], fontSize=8.5, leading=11)
WARN = ParagraphStyle("WARN", parent=SS["BodyText"], textColor=colors.white, backColor=colors.HexColor("#b91c1c"),
                      borderPadding=5, fontSize=10, leading=13)
DEC_COLOR = {"PASS": "#15803d", "REVIEW": "#b45309", "FAIL": "#b91c1c"}


def _img(path: str, width_mm: float = 80):
    try:
        im = Image.open(storage_file(path)).convert("RGB")
    except Exception:  # noqa: BLE001
        return Paragraph("(image unavailable)", SM)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    buf.seek(0)
    w = width_mm * mm
    return RLImage(buf, width=w, height=w * im.height / im.width)


def _tbl(rows, widths=None, header=False):
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    st = [("FONTSIZE", (0, 0), (-1, -1), 8.5), ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
          ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")])]
    if header:
        st += [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]
    t.setStyle(TableStyle(st))
    return t


def _audit_hash(db: Session, inspection_id: int) -> str:
    ev = db.execute(select(AuditEvent).where(AuditEvent.inspection_id == inspection_id, AuditEvent.event_type == "INSPECTION")).scalars().first()
    return ev.record_hash if ev else "n/a"


def inspection_pdf(db: Session, i: Inspection) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm, bottomMargin=14 * mm,
                            title=f"Inspection {i.uid}")
    el = [Paragraph("AI-Based Automated Visual Inspection System", H1), Paragraph("Individual Inspection Report", SS["Heading3"])]
    if i.simulated:
        el += [Paragraph("DEMO MODE - SIMULATED RESULT. This inspection was produced by the demonstration engine and is NOT a trained-AI prediction.", WARN), Spacer(1, 4)]
    col = DEC_COLOR[i.decision.value]
    el.append(Paragraph(f'Decision: <font color="{col}"><b>{i.decision.value}</b></font>', SS["Heading2"]))
    imgs = {im.kind: im.path for im in i.images}
    rows = [["Inspection ID", f"{i.id} ({i.uid})"], ["Date / time (UTC)", iso(i.created_at)], ["Product", f"{i.product.name} ({i.product.category})"],
            ["Product / serial ID", i.product_code or "-"], ["Batch ID", i.batch_code or "-"], ["Production line", i.line_id or "-"],
            ["Inspection mode", i.mode.value.upper() + (" (simulated)" if i.simulated else "")], ["Model version", i.model_version],
            ["Anomaly score", f"{i.score:.4f}"], ["Review / fail thresholds", f"{i.review_threshold:.2f} / {i.fail_threshold:.2f} (Provisional)"],
            ["Defect category", (i.defect_class if i.defect_class != "unclassified_anomaly" else "Anomaly detected (PatchCore)") or "-"],
            ["Classifier confidence", f"{i.confidence:.2f}" if i.confidence is not None else "n/a (PatchCore Anomaly Detection)"],
            ["Inference latency", f"{i.latency_ms:.1f} ms"], ["Image SHA-256", i.image_sha256]]
    if i.final_decision:
        r = i.reviews[-1] if i.reviews else None
        rows.append(["Final (human) decision", f"{i.final_decision.value} by {r.reviewer_name if r else '-'}"])
    rows.append(["Audit record hash", _audit_hash(db, i.id)])
    el.append(_tbl([[Paragraph(str(a), SM), Paragraph(str(b), SM)] for a, b in rows], [48 * mm, 130 * mm]))
    cells = [[_img(imgs["original"], 80) if "original" in imgs else "", _img(imgs["annotated"], 80) if "annotated" in imgs else ""],
             [Paragraph("Original acquisition", SM), Paragraph("Annotated (defect ellipses / circles)", SM)],
             [_img(imgs["heatmap"], 80) if "heatmap" in imgs else "", _img(imgs["overlay"], 80) if "overlay" in imgs else ""],
             [Paragraph("PatchCore anomaly heatmap", SM), Paragraph("Heatmap overlay", SM)]]
    el.append(Table(cells, colWidths=[88 * mm, 88 * mm]))

    # Localized Defect Regions Table
    try:
        expl = json.loads(i.explanation_json or "{}")
    except Exception:
        expl = {}
    regions = expl.get("regions", [])

    el.append(Paragraph("Detected Defect Regions (Circles / Ellipses)", H2))
    if regions:
        reg_rows = [["#", "Geometry & Shape", "Box [X,Y,W,H]", "Peak Score", "Defect Label", "Confidence"]]
        for r in regions:
            shape_str = f"{r.get('shape', 'ellipse').title()} @ ({r.get('center', [0,0])[0]:.0f}, {r.get('center', [0,0])[1]:.0f})"
            box_str = f"[{r.get('box', [0,0,0,0])[0]}, {r.get('box', [0,0,0,0])[1]}, {r.get('box', [0,0,0,0])[2]}, {r.get('box', [0,0,0,0])[3]}]"
            conf_str = f"{r.get('confidence')*100:.0f}%" if r.get("confidence") is not None else "n/a (PatchCore)"
            lbl = "Unclassified anomaly" if r.get("label") == "unclassified_anomaly" else str(r.get("label", "")).title()
            reg_rows.append([
                f"#{r.get('id', 1)}",
                Paragraph(shape_str, SM),
                Paragraph(box_str, SM),
                f"{r.get('peak_score', 0):.3f}",
                Paragraph(lbl, SM),
                conf_str
            ])
        el.append(_tbl([[Paragraph(str(c), SM) for c in row] for row in reg_rows],
                       [10 * mm, 45 * mm, 35 * mm, 22 * mm, 42 * mm, 24 * mm], header=True))
        el.append(Spacer(1, 3))
        el.append(Paragraph(
            "Defect labels are reported as 'Unclassified anomaly' because no trained multi-class classifier is attached. "
            "Regions are localized via PatchCore nearest-neighbour feature distance thresholding.", SM))
    else:
        el.append(Paragraph("No suspicious defect clusters exceeded the anomaly localization threshold. (Absence of localized regions does not imply product is defect-free if overall anomaly score is elevated.)", SM))

    if i.reviews:
        el.append(Paragraph("Human review history", H2))
        el.append(_tbl([["When (UTC)", "Reviewer", "Decision", "Comment"]] + [[iso(r.created_at), r.reviewer_name, r.decision.value, Paragraph(r.comment or "-", SM)] for r in i.reviews],
                       [38 * mm, 32 * mm, 24 * mm, 84 * mm], header=True))
    el.append(Spacer(1, 6))
    el.append(Paragraph(f"Generated {iso(utcnow())}. The original AI decision is preserved separately from any human decision.", SM))
    doc.build(el)
    return buf.getvalue()


def batch_pdf(db: Session, batch: InspectionBatch, items: list[Inspection]) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm, bottomMargin=14 * mm,
                            title=f"Batch {batch.batch_code}")
    cnt = {k: sum(1 for x in items if x.decision.value == k) for k in ("PASS", "REVIEW", "FAIL")}
    el = [Paragraph("AI-Based Automated Visual Inspection System", H1), Paragraph("Batch Quality Report", SS["Heading3"])]
    if any(x.simulated for x in items) or batch.mode.value == "demo":
        el += [Paragraph("DEMO MODE - SIMULATED RESULTS. Not produced by a trained AI model.", WARN), Spacer(1, 4)]
    el.append(_tbl([[Paragraph(str(a), SM), Paragraph(str(b), SM)] for a, b in [
        ["Batch ID", batch.batch_code], ["Product", batch.product.name], ["Production line", batch.line_id or "-"], ["Mode", batch.mode.value],
        ["Inspections", len(items)], ["PASS / REVIEW / FAIL", f'{cnt["PASS"]} / {cnt["REVIEW"]} / {cnt["FAIL"]}'],
        ["Report generated (UTC)", iso(utcnow())]]], [48 * mm, 130 * mm]))
    if items:
        d = Drawing(180 * mm, 55 * mm)
        pie = Pie()
        pie.x, pie.y, pie.width, pie.height = 10, 5, 90, 90
        vals = [(k, v) for k, v in cnt.items() if v]
        pie.data, pie.labels = [v for _, v in vals], [f"{k} ({v})" for k, v in vals]
        for n, (k, _) in enumerate(vals):
            pie.slices[n].fillColor = colors.HexColor(DEC_COLOR[k])
        d.add(pie)
        defects: dict[str, int] = {}
        for x in items:
            if x.defect_class:
                defects[x.defect_class] = defects.get(x.defect_class, 0) + 1
        if defects:
            bar = VerticalBarChart()
            bar.x, bar.y, bar.width, bar.height = 330, 12, 180, 80
            bar.data = [list(defects.values())]
            bar.categoryAxis.categoryNames = list(defects.keys())
            bar.categoryAxis.labels.fontSize = 6
            bar.bars[0].fillColor = CYAN
            d.add(bar)
        el += [Paragraph("Decision and defect distribution", H2), d]
    el.append(Paragraph("Inspection summary", H2))
    rows = [["ID", "Item", "Score", "Decision", "Defect", "Final", "Mode"]]
    for x in items:
        rows.append([x.id, Paragraph(x.product_code or "-", SM), f"{x.score:.3f}", x.decision.value, x.defect_class or "-",
                     x.final_decision.value if x.final_decision else "-", x.mode.value])
    el.append(_tbl(rows, [14 * mm, 52 * mm, 18 * mm, 22 * mm, 36 * mm, 18 * mm, 16 * mm], header=True))
    doc.build(el)
    return buf.getvalue()


def inspections_dataframe(items: list[Inspection]) -> pd.DataFrame:
    return pd.DataFrame([{
        "id": x.id, "uid": x.uid, "created_at_utc": iso(x.created_at), "mode": x.mode.value, "simulated": x.simulated,
        "product": x.product.name, "product_code": x.product_code, "batch_code": x.batch_code, "line_id": x.line_id,
        "anomaly_score": x.score, "decision": x.decision.value, "defect_class": x.defect_class or "",
        "confidence": x.confidence if x.confidence is not None else "", "review_threshold": x.review_threshold,
        "fail_threshold": x.fail_threshold, "model_version": x.model_version, "latency_ms": x.latency_ms,
        "review_status": x.review_status.value, "final_decision": x.final_decision.value if x.final_decision else "",
        "image_sha256": x.image_sha256} for x in items])


def csv_bytes(items: list[Inspection]) -> bytes:
    return inspections_dataframe(items).to_csv(index=False).encode("utf-8")
