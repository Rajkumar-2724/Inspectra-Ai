import cv2
import numpy as np

img = cv2.imread(r"C:\Users\rkraj\paper_dataset\test\dot\0d7b1323-6f2c-4699-b7c4-bef207b2d712.jpg")
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

print("test_dot_1 at (565, 771):")
patch1 = gray[760:780, 555:575]
print("  Patch 1 min:", patch1.min(), "mean:", patch1.mean())

print("test_dot_1 at (254, 1259):")
patch2 = gray[1250:1270, 245:265]
print("  Patch 2 min:", patch2.min(), "mean:", patch2.mean())

# Also inspect train_good_1 borders:
tg1 = cv2.imread(r"C:\Users\rkraj\paper_dataset\train\good\0bdedfdc-f724-48ad-8a24-9c176da13c30.jpg")
tg1_gray = cv2.cvtColor(tg1, cv2.COLOR_BGR2GRAY)
print("train_good_1 absolute min pixel:", tg1_gray.min(), "at loc:", np.unravel_index(np.argmin(tg1_gray), tg1_gray.shape))
