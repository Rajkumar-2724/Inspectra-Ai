# PCB1 Model Directory (`AI-Visual-Inspection`)

This directory is designated for the **VisA PCB1 PatchCore** anomaly detection model trained using the Google Colab notebook:
`notebooks/PatchCore_VisA_PCB1_Training.ipynb`

## Expected Model Artifacts
Once training and export in Google Colab finish, download `patchcore_pcb1_bundle.zip` and place the following files into this directory:
1. `patchcore_pcb1_v1.onnx` — Exported ONNX model graph with embedded coreset memory bank (`~92-150 MB`).
2. `patchcore_pcb1_v1.meta.json` — Model metadata sidecar with calibrated thresholds, dimensions, and SHA-256 hash.

## Activating the Model in the Inspection Platform
1. Ensure the files exist at:
   - `models/pcb1/patchcore_pcb1_v1.onnx`
   - `models/pcb1/patchcore_pcb1_v1.meta.json`
2. Add or uncomment the entry in `models/registry.yaml`:
   ```yaml
     - name: patchcore-pcb1
       version: "1.0"
       type: patchcore
       format: onnx
       file: pcb1/patchcore_pcb1_v1.onnx
       product: "PCB Controller Board"
       assign: true
   ```
3. Run model registration from `backend/`:
   ```bash
   .venv\Scripts\python.exe -m app.scripts.register_models
   ```
4. Start the application (`start_all.bat`) or view the Web Dashboard:
   - **PCB Controller Board** will automatically transition to **Real Mode: READY**.
   - Inspected PCB images will display genuine PatchCore distance heatmaps, fitted defect circles/ellipses, and honest `Unclassified anomaly` labels.

## Operational Constraints & Scope
- **Domain Scope**: Trained strictly on the Amazon VisA PCB1 layout and component positioning.
- **Illumination & Fixture**: Requires consistent industrial diffuse top lighting and fixed-distance camera alignment matching VisA acquisition standards.
- **Webcam / Hand-held**: Does not support arbitrary consumer circuit board designs, varying camera perspectives, or uncontrolled hand-held lighting.
- **Classification**: Detects anomalous surface and component alterations; specific defect type classification requires an attached multi-class classifier.
