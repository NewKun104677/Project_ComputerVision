import os
import sys

os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

import cv2
import tkinter as tk
from PIL import Image, ImageTk
import json
import time
import threading
from deepface import DeepFace

IP_camera = '192.168.1.108'
url = 'rtsp://admin:p@ssw0rd@' + IP_camera + ':554/cam/realmonitor?channel=1&subtype=1'     # mainstream subtype = 0 , substream subtype = 1


class FaceScannerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ด่านที่ 1: ระบบสแกนใบหน้า (Masked Face Recognition)")
        # --- คำนวณขนาดหน้าจอและจัดให้อยู่ครึ่งขวา ---
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        half_width = screen_width // 2
        
        # บวกตำแหน่ง X เข้าไปเท่ากับครึ่งจอ เพื่อให้หน้าต่างไปเริ่มที่ครึ่งขวาพอดี
        self.root.geometry(f"{half_width}x{screen_height}+{half_width}+0")
        
        self.root.configure(bg="#f0f0f0")

        self.action_type = None
        self.scan_active = False
        self.db_path = "employee_db"
        self.is_camera_active = True 
        
        # ตัวแปรใหม่ ป้องกันปัญหา Ghost Thread
        self.scan_session_id = None 

        if not os.path.exists(self.db_path):
            os.makedirs(self.db_path)
            print(f"สร้างโฟลเดอร์ {self.db_path} แล้ว")

        # --- UI Components ---
        self.title_label = tk.Label(root, text="ระบบระบุตัวตนพนักงาน", font=("Helvetica", 24, "bold"), bg="#f0f0f0")
        self.title_label.pack(pady=10)

        self.video_label = tk.Label(root, bg="black")
        self.video_label.pack(pady=10)

        self.status_label = tk.Label(root, text="กรุณาเลือกทำรายการ (สแกนเข้า / สแกนออก)", font=("Helvetica", 16), bg="#f0f0f0", fg="#333333")
        self.status_label.pack(pady=10)

        btn_frame = tk.Frame(root, bg="#f0f0f0")
        btn_frame.pack(pady=10)

        self.btn_in = tk.Button(btn_frame, text="สแกนเข้า (IN)", font=("Helvetica", 16, "bold"), bg="#4CAF50", fg="white", width=15, command=lambda: self.start_scan("IN"))
        self.btn_in.pack(side=tk.LEFT, padx=20)

        self.btn_out = tk.Button(btn_frame, text="สแกนออก (OUT)", font=("Helvetica", 16, "bold"), bg="#F44336", fg="white", width=15, command=lambda: self.start_scan("OUT"))
        self.btn_out.pack(side=tk.LEFT, padx=20)
        
        # เพิ่มปุ่มรีเซ็ต
        self.btn_reset = tk.Button(btn_frame, text="🔄 รีเซ็ต (Reset)", font=("Helvetica", 16, "bold"), bg="#9E9E9E", fg="white", width=15, command=self.manual_reset)
        self.btn_reset.pack(side=tk.LEFT, padx=20)

        # --- Camera Setup ---
        self.cap = cv2.VideoCapture(url)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        self.update_camera()

    def start_scan(self, action):
        self.action_type = action
        self.scan_active = True
        
        # สร้าง ID ของรอบการสแกนนี้ (ใช้เวลา ณ ตอนที่กดปุ่มเป็นรหัส)
        self.scan_start_time = time.time()
        self.scan_session_id = self.scan_start_time 
        
        action_text = "เข้าไลน์ผลิต" if action == "IN" else "ออกจากไลน์ผลิต"
        self.status_label.config(text=f"กำลังสแกนเพื่อ '{action_text}'...\nกรุณามองกล้อง (มีเวลา 15 วินาที)", fg="blue")
        
        self.btn_in.config(state=tk.DISABLED)
        self.btn_out.config(state=tk.DISABLED)

    def update_camera(self):
        if self.is_camera_active and self.cap is not None and self.cap.isOpened():
            success, frame = self.cap.read()
            if success:
                # 1. บังคับย่อขนาดภาพก่อนทำอย่างอื่นเลย (แก้ภาพล้นจอ และลดภาระ DeepFace)
                frame = cv2.resize(frame, (640, 480))
                
                # 2. พลิกภาพกระจก
               

                if self.scan_active:
                    elapsed_time = time.time() - self.scan_start_time
                    
                    if elapsed_time > 60:  
                        self.process_timeout()
                    else:
                        # --- สร้างข้อความและตั้งค่าฟอนต์ ---
                        text = f"AI is Processing... {int(60 - elapsed_time)}s"
                        font = cv2.FONT_HERSHEY_SIMPLEX
                        font_scale = 0.7
                        thickness = 2
                        
                        # --- คำนวณหาจุดกึ่งกลาง (Center X) ---
                        text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
                        text_x = (frame.shape[1] - text_size[0]) // 2
                        text_y = 35  # ระยะห่างจากขอบจอด้านบน
                        
                        # --- วางข้อความลงบนภาพ ---
                        cv2.putText(frame, text, (text_x, text_y), font, font_scale, (0, 255, 255), thickness)

                        # เช็กว่ามี Thread ว่างไหม ถึงจะส่งภาพไปให้ทำ
                        if not hasattr(self, 'ai_thread') or not self.ai_thread.is_alive():
                            scan_frame = frame.copy()
                            # ส่งรหัส session_id เข้าไปพร้อมกับภาพด้วย
                            self.ai_thread = threading.Thread(target=self.recognize_face, args=(scan_frame, self.scan_session_id))
                            self.ai_thread.start()

                cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(cv2image)
                imgtk = ImageTk.PhotoImage(image=img)
                self.video_label.imgtk = imgtk
                self.video_label.configure(image=imgtk)

        self.root.after(15, self.update_camera)

    def recognize_face(self, frame, session_id):
        try:
            dfs = DeepFace.find(img_path=frame, 
                                db_path=self.db_path, 
                                model_name="ArcFace",
                                detector_backend="mtcnn", 
                                enforce_detection=False,
                                silent=True)
            
            if len(dfs) > 0 and not dfs[0].empty:
                matched_file = dfs[0].iloc[0]['identity']
                emp_id = os.path.basename(matched_file).split('.')[0]
                self.root.after(0, lambda: self.handle_ai_result(True, emp_id, session_id))
            else:
                self.root.after(0, lambda: self.handle_ai_result(False, "ไม่พบใบหน้าที่ตรงกัน", session_id))
        
        except Exception as e:
            self.root.after(0, lambda: self.handle_ai_result(False, f"ระบบขัดข้อง: {str(e)[:30]}...", session_id))

    def handle_ai_result(self, success, data, session_id):
        # *** หัวใจสำคัญ *** 
        # ถ้าผลลัพธ์ที่ AI ส่งกลับมา เป็นของรอบการสแกนเก่า (ที่หมดเวลาไปแล้ว) ให้เมินทิ้งไปเลย ไม่ต้องแสดงผล
        if not self.scan_active or session_id != self.scan_session_id:
            return

        if success:
            self.process_success(data)
        else:
            self.process_fail(data)

    def process_success(self, emp_id):
        self.scan_active = False
        self.is_camera_active = False 
        
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()
            self.cap = None
            
        data = {
            "emp_id": emp_id,
            "action_type": self.action_type
        }
        with open("current_scan.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            
        self.status_label.config(text=f"✅ ยืนยันตัวตนสำเร็จ!\nรหัส: {emp_id}\nกำลังสลับกล้องไปด่านตรวจชุด...", fg="green")
        self.video_label.configure(image='')
        self.root.after(1000, self.wait_for_ppe_finish)

    def wait_for_ppe_finish(self):
        if not os.path.exists("current_scan.json"):
            time.sleep(0.5)
            self.cap = cv2.VideoCapture(url)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.is_camera_active = True 
            self.reset_gui()
        else:
            self.root.after(1000, self.wait_for_ppe_finish)

    def process_fail(self, error_msg):
        self.status_label.config(text=f"❌ {error_msg}\nกำลังพยายามสแกนใหม่...", fg="red")

    def process_timeout(self):
        self.scan_active = False
        self.scan_session_id = None # ยกเลิกรหัสรอบนี้
        self.status_label.config(text="⏱️ หมดเวลาสแกน! ระบบได้ทำการยกเลิกรายการ\nกรุณากดปุ่มทำรายการใหม่อีกครั้ง", fg="orange")
        self.btn_in.config(state=tk.NORMAL)
        self.btn_out.config(state=tk.NORMAL)

    def manual_reset(self):
        if os.path.exists("current_scan.json"):
            os.remove("current_scan.json")
            
        if self.cap is None or not self.cap.isOpened():
            self.cap = cv2.VideoCapture(url)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            
        self.is_camera_active = True
        self.reset_gui()
        self.status_label.config(text="รีเซ็ตระบบเรียบร้อยแล้ว กรุณาทำรายการใหม่", fg="green")

    def reset_gui(self):
        self.action_type = None
        self.scan_active = False
        self.scan_session_id = None
        self.status_label.config(text="กรุณาเลือกทำรายการ (สแกนเข้า / สแกนออก)", fg="#333333")
        self.btn_in.config(state=tk.NORMAL)
        self.btn_out.config(state=tk.NORMAL)

if __name__ == "__main__":
    root = tk.Tk()
    app = FaceScannerApp(root)
    root.mainloop()