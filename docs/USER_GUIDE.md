# User guide

**Sign in** with the seeded admin (see SETUP). New self-registered users are Quality Inspectors; admins assign roles under *Settings*.

**Modes.** The top bar toggles *Demo* / *Real AI*. Real AI is disabled until a product has valid model artifacts (*Models* page explains why not). Demo results are produced by a deterministic simulator and are marked SIMULATED on screen, in PDFs, CSV (`simulated` column) and analytics.

**AI Inspection.** Pick a product, drop an image (or, in demo mode, click a synthetic sample), choose a demo scenario (Good → PASS, Obvious defect → FAIL, Subtle → REVIEW, Unknown → REVIEW, Lighting/rotation → PASS; “Auto” derives it from the image hash), run. Switch between Original / Processed / Heatmap / Overlay / Boxes / Reference, zoom, download the current view, open the PDF report. In demo mode the scenario — not the image content — decides the outcome.

**Live Camera.** Start camera, capture a frame, inspect it; optionally enable timed capture (≥2 s). Only one request is in flight; frames arriving while busy are skipped and counted. Measured round-trip time and rate are shown.

**Batch.** Choose product + batch ID, drop up to 200 images, watch progress, filter by decision, retry failed images, export CSV/PDF.

**Human review.** REVIEW results land in the queue. Approve / Reject (comment required) / Request reinspection. The AI decision stays on record next to the human one.

**Products** (admin): thresholds, defect classes, reference image, model assignment, archive. **Models** (admin): register & validate artifacts. **Audit trail**: browse records, admin can *Verify chain*.

**Analytics.** Defect counts/trends, product/batch/line comparisons, flagged-region grid, review rate, latency. Accuracy-type metrics are intentionally absent; false-pass/false-fail appear only after you label inspections as good/defective.
