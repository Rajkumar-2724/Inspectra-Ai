import os
import zipfile
from PIL import Image
import numpy as np

zip_path = r"C:\Users\rkraj\paper_dataset.zip"
folder_path = r"C:\Users\rkraj\paper_dataset"

print(f"Zip exists: {os.path.exists(zip_path)}")
print(f"Folder exists: {os.path.exists(folder_path)}")

if os.path.exists(zip_path):
    print("\n--- ZIP Contents ---")
    with zipfile.ZipFile(zip_path, "r") as z:
        for info in z.infolist():
            print(f"{info.filename:45s} size={info.file_size} bytes")

print("\n--- Folder Inspection ---")
for root, dirs, files in os.walk(folder_path):
    for f in files:
        full_p = os.path.join(root, f)
        rel_p = os.path.relpath(full_p, folder_path)
        try:
            img = Image.open(full_p)
            arr = np.array(img)
            print(f"{rel_p:40s} | format={img.format} | size={img.size} (WxH) | mode={img.mode} | min={arr.min()}, max={arr.max()}, mean={arr.mean():.2f}")
        except Exception as e:
            print(f"{rel_p:40s} | ERROR: {e}")
