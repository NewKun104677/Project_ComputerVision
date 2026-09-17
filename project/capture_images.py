import cv2
import os
import time
import sys
import tkinter as tk
from tkinter import simpledialog

# แก้ปัญหาภาษาไทยใน Terminal
sys.stdout.reconfigure(encoding='utf-8')

# --- สร้างกล่อง Pop-up เด้งถามจำนวนรูป ---
root = tk.Tk()
root.withdraw() # ซ่อนหน้าต่างหลักของ Tkinter ไว้

max_images = simpledialog.askinteger(
    "ตั้งค่าการถ่ายรูป", 
    "🎯 กรุณาระบุจำนวนรูปภาพที่ต้องการถ่าย:",
    initialvalue=50,
    minvalue=1
)

# ถ้าผู้ใช้กดยกเลิกหรือไม่ใส่ตัวเลข ให้ปิดโปรแกรม
if not max_images:
    print("ยกเลิกการทำงาน")
    sys.exit()

# ชื่อโฟลเดอร์สำหรับเก็บภาพ
save_folder = "dataset_images"
if not os.path.exists(save_folder):
    os.makedirs(save_folder)

# เปิดกล้อง
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

print(f"\n=== 📸 เริ่มต้นการถ่ายรูป (เป้าหมาย: {max_images} รูป) ===")
print("👉 คลิกที่หน้าต่างกล้อง แล้วกด 'Spacebar' เพื่อถ่ายรูป")
print("👉 กดปุ่ม 'ESC' เพื่อปิดโปรแกรม")

img_count = 1

while True:
    success, frame = cap.read()
    if not success:
        print("❌ ไม่สามารถอ่านภาพจากกล้องได้")
        break

    frame = cv2.flip(frame, 1)
    display_frame = frame.copy()
    
    # แสดงจำนวนรูปที่ถ่ายไปแล้ว
    cv2.putText(display_frame, f"Captured: {img_count - 1} / {max_images}", (10, 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    cv2.putText(display_frame, "Press SPACE to Capture | ESC to Exit", (10, 60), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    cv2.imshow("Dataset Capture", display_frame)

    key = cv2.waitKey(1) & 0xFF

    if key == 32:  # Spacebar
        timestamp = int(time.time())
        filename = f"{save_folder}/ppe_{timestamp}_{img_count}.jpg"
        
        cv2.imwrite(filename, frame)
        print(f"✅ บันทึกรูปที่ {img_count}/{max_images}: {filename}")
        
        # เอฟเฟกต์แฟลชสีขาว
        flash = frame.copy()
        flash[:] = (255, 255, 255)
        cv2.imshow("Dataset Capture", flash)
        cv2.waitKey(40)

        if img_count >= max_images:
            print(f"\n🎉 ถ่ายรูปครบ {max_images} รูปเรียบร้อยแล้ว!")
            break
            
        img_count += 1

    elif key == 27:  # ESC
        print("\n🛑 ปิดโปรแกรม")
        break

cap.release()
cv2.destroyAllWindows()        