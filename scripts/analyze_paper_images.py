import cv2
import numpy as np

folder = r"C:\Users\rkraj\paper_dataset"

images = {
    "train_good_1": r"train\good\0bdedfdc-f724-48ad-8a24-9c176da13c30.jpg",
    "train_good_2": r"train\good\c8491c4d-450f-40b5-887a-a5bae69a33fe.jpg",
    "test_dot_1": r"test\dot\0d7b1323-6f2c-4699-b7c4-bef207b2d712.jpg",
    "test_dot_2": r"test\dot\27ed0321-16c9-4f0e-84c2-bf337463b4cd.jpg",
}

for name, rel_path in images.items():
    full_p = f"{folder}\\{rel_path}"
    img = cv2.imread(full_p)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    print(f"=== {name} ({w}x{h}) ===")
    
    # Border analysis (top 20px, bottom 20px, left 20px, right 20px)
    borders = {
        "top": gray[:20, :].mean(),
        "bottom": gray[-20:, :].mean(),
        "left": gray[:, :20].mean(),
        "right": gray[:, -20:].mean(),
        "center": gray[int(h*0.2):int(h*0.8), int(w*0.2):int(w*0.8)].mean()
    }
    print("  Borders vs Center mean brightness:", {k: f"{v:.1f}" for k, v in borders.items()})
    
    # Darkest spots in interior (excluding 30px outer boundary)
    inner = gray[30:-30, 30:-30]
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(inner)
    actual_min_loc = (min_loc[0] + 30, min_loc[1] + 30)
    print(f"  Interior Min Pixel: {min_val} at (x={actual_min_loc[0]}, y={actual_min_loc[1]})")
    
    # Check thresholded dark blobs in interior
    dark_mask = (inner < (inner.mean() - 40)).astype(np.uint8)
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(dark_mask)
    print(f"  Dark blobs (< mean-40): {num_labels - 1} found")
    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        bx, by = stats[i, cv2.CC_STAT_LEFT] + 30, stats[i, cv2.CC_STAT_TOP] + 30
        bw, bh = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
        print(f"    Blob {i}: area={area} px, bbox=[x={bx}, y={by}, w={bw}, h={bh}]")
