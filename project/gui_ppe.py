import cv2
import tkinter as tk
from PIL import Image, ImageTk
import json
import os
import mysql.connector
import threading
import webbrowser
import time
from ultralytics import YOLO

IP_camera = '192.168.1.108'
url = 'rtsp://admin:p@ssw0rd@' + IP_camera + ':554/cam/realmonitor?channel=1&subtype=1'     # mainstream subtype = 0 , substream subtype = 1


class PPEInspectorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ด่านที่ 2: ระบบตรวจสอบการแต่งกาย (YOLOv8 & DB Logging)")
        # --- คำนวณขนาดหน้าจอและจัดให้อยู่ครึ่งซ้าย ---
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        half_width = screen_width // 2
        
        # รูปแบบ geometry คือ "กว้างxสูง+ตำแหน่งX+ตำแหน่งY"
        self.root.geometry(f"{half_width}x{screen_height}+0+0")
        
        self.root.configure(bg="#e8f4f8")

        self.db_config = {
            "host": "localhost",
            "user": "root",
            "password": "",
            "database": "cleanroom_db"
        }

        print("กำลังโหลดโมเดล YOLO26...")
        self.yolo_model = YOLO('yolo26n.pt') 

        self.cap = None
        self.current_frame = None
        self.is_camera_running = False
        self.ppe_start_time = None
        self.last_person_seen_time = None
        
        # --- ตัวแปรสำหรับจำข้อมูลเพื่อส่งลง Database ---
        self.current_emp_id = None
        self.current_action_type = None

        # --- UI Components ---
        self.title_label = tk.Label(root, text="ระบบตรวจสอบความเรียบร้อย (YOLO PPE)", font=("Helvetica", 22, "bold"), bg="#e8f4f8")
        self.title_label.pack(pady=10)

        self.info_frame = tk.Frame(root, bg="white", relief=tk.RIDGE, bd=2)
        self.info_frame.pack(pady=10, padx=20, fill=tk.X)
        
        self.emp_info_label = tk.Label(self.info_frame, text="รอรับข้อมูลจากด่านสแกนหน้า...", font=("Helvetica", 16), bg="white", fg="gray")
        self.emp_info_label.pack(pady=10)

        self.video_label = tk.Label(root, bg="black")
        self.video_label.pack(pady=10)

        self.result_label = tk.Label(root, text="สถานะ: รอพนักงานเข้ากล้อง", font=("Helvetica", 16, "bold"), bg="#e8f4f8", fg="#333333")
        self.result_label.pack(pady=10)
        
        # --- ปุ่มควบคุมระบบ ---
        btn_frame = tk.Frame(root, bg="#e8f4f8")
        btn_frame.pack(pady=5)
        
        # ปุ่มจำลองให้ผ่าน (สำหรับเทสต์ระบบ Database)
        self.btn_pass = tk.Button(btn_frame, text="✅ จำลองตรวจผ่าน (Test PASS)", font=("Helvetica", 14, "bold"), bg="#4CAF50", fg="white", command=self.simulate_pass)
        self.btn_pass.pack(side=tk.LEFT, padx=10)
        
        self.btn_reset = tk.Button(btn_frame, text="🔄 ยกเลิกคิว (Reset)", font=("Helvetica", 14, "bold"), bg="#F44336", fg="white", command=self.manual_reset)
        self.btn_reset.pack(side=tk.LEFT, padx=10)

        # --- เพิ่มปุ่มเปิดหน้าเว็บตรงนี้ ---
        self.btn_dashboard = tk.Button(btn_frame, text="🌐 เปิดหน้าเว็บ (Dashboard)", font=("Helvetica", 14, "bold"), bg="#2196F3", fg="white", command=self.open_dashboard)
        self.btn_dashboard.pack(side=tk.LEFT, padx=10)

        self.check_json_loop()
        self.update_gui_loop()
        self.timeout_monitor_loop()

    def camera_thread_logic(self):
        frame_counter = 0
        last_boxes = [] 
        
        # ✅ ตัวแปรสำหรับนับ FPS แบบ 1 วินาที (ทำให้ตัวเลขแสดงผลนิ่ง)
        fps_start_time = time.time()
        fps_frame_count = 0
        display_fps = 0
        
        while self.is_camera_running and self.cap is not None and self.cap.isOpened():
            success, frame = self.cap.read()
            if success:
                frame = cv2.resize(frame, (640, 480))
                
                frame_counter += 1
                fps_frame_count += 1
                person_detected = False

                if frame_counter % 3 == 0:
                    results = self.yolo_model(frame, classes=[0], verbose=False)
                    last_boxes = [] 
                    for r in results:
                        boxes = r.boxes
                        for box in boxes:
                            last_boxes.append(tuple(map(int, box.xyxy[0])))
                            
                # ✅ แก้ปัญหากรอบเยอะเกินไป: เลือกวาดเฉพาะกรอบที่ "ใหญ่ที่สุด" (คนที่ใกล้กล้องสุด)
                if last_boxes:
                    # คำนวณหาพื้นที่ (กว้าง x ยาว) ของแต่ละกรอบ แล้วเลือกอันที่พื้นที่เยอะสุด
                    largest_box = max(last_boxes, key=lambda b: (b[2]-b[0]) * (b[3]-b[1]))
                    x1, y1, x2, y2 = largest_box
                    person_detected = True
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, "Person", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                current_time = time.time()
                
                # ✅ คำนวณ FPS โดยรีเฟรชตัวเลขทุกๆ 1 วินาที
                if current_time - fps_start_time >= 1.0:
                    display_fps = fps_frame_count
                    fps_frame_count = 0
                    fps_start_time = current_time
                
                cv2.putText(frame, f"FPS: {display_fps}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)
                
                if person_detected:
                    self.last_person_seen_time = current_time
                    
                if self.ppe_start_time is not None:
                    time_left = max(0, 30 - int(current_time - self.ppe_start_time))
                    text = f"Time left: {time_left}s"
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    font_scale = 0.7
                    thickness = 2
                    text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
                    text_x = (frame.shape[1] - text_size[0]) // 2
                    
                    # ✅ ย้ายข้อความเวลามาไว้ "ด้านล่างจอ" เพื่อไม่ให้ทับหัวคนและตัวหนังสือของกล้อง
                    text_y = 450 
                    cv2.putText(frame, text, (text_x, text_y), font, font_scale, (0, 165, 255), thickness)

                self.current_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # ✅ ใส่ตัวหน่วงเวลาเล็กน้อย เพื่อบังคับไม่ให้ลูปหมุนเร็วกว่าที่กล้องส่งภาพมา (แก้ FPS 160+)
                time.sleep(0.01)

        if self.cap is not None:
            self.cap.release()
            self.cap = None
            
            

    def update_gui_loop(self):
        if self.current_frame is not None and self.is_camera_running:
            img = Image.fromarray(self.current_frame)
            imgtk = ImageTk.PhotoImage(image=img)
            self.video_label.imgtk = imgtk
            self.video_label.configure(image=imgtk)
        
        self.root.after(15, self.update_gui_loop)

    def timeout_monitor_loop(self):
        if self.is_camera_running and self.ppe_start_time is not None and self.last_person_seen_time is not None:
            current_time = time.time()
            
            if current_time - self.last_person_seen_time > 5:
                print("ยกเลิกคิว: ไม่พบพนักงานอยู่หน้ากล้อง")
                self.result_label.config(text="❌ ยกเลิก: ไม่พบพนักงานอยู่หน้ากล้อง", fg="red")
                self.finish_ppe_inspection(status="FAIL", missing_items="พนักงานเดินออกจากกล้องก่อนตรวจเสร็จ")
                
            elif current_time - self.ppe_start_time > 30:
                print("หมดเวลาตรวจชุด")
                self.result_label.config(text="❌ ไม่ผ่าน: หมดเวลาตรวจชุด 30 วินาที", fg="red")
                self.finish_ppe_inspection(status="FAIL", missing_items="ใช้เวลาตรวจชุดเกิน 30 วินาที")
                
        self.root.after(1000, self.timeout_monitor_loop)

    def check_json_loop(self):
        json_file = "current_scan.json"
        
        if os.path.exists(json_file) and not self.is_camera_running:
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # --- เก็บข้อมูลไว้ในหน่วยความจำเตรียมลง DB ---
                self.current_emp_id = data.get("emp_id")
                self.current_action_type = data.get("action_type")
                
                emp_name = self.get_employee_name(self.current_emp_id)
                
                self.emp_info_label.config(text=f"👤 รหัส: {self.current_emp_id} | ชื่อ: {emp_name}\n(กำลังบันทึกสถานะ: {self.current_action_type})", fg="blue")
                self.result_label.config(text="ระบบกำลังตรวจจับ: กรุณายืนให้อยู่ในกรอบ", fg="orange")
                
                self.cap = cv2.VideoCapture(url)
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                
                self.ppe_start_time = time.time()
                self.last_person_seen_time = time.time()
                
                self.is_camera_running = True
                threading.Thread(target=self.camera_thread_logic, daemon=True).start()
                
            except Exception as e:
                print("Error reading JSON:", e)

        self.root.after(1000, self.check_json_loop)

    # --- ฟังก์ชันบันทึกข้อมูลลง Database ---
    def save_log_to_db(self, status, missing_items):
        if not self.current_emp_id:
            return
            
        try:
            conn = mysql.connector.connect(**self.db_config)
            cursor = conn.cursor()
            
            # ไม่ต้องส่งเวลาเข้าไป เพราะฐานข้อมูลถูกตั้งให้ใช้ CURRENT_TIMESTAMP อัตโนมัติ
            query = """INSERT INTO entry_logs (emp_id, action_type, status, missing_items) 
                       VALUES (%s, %s, %s, %s)"""
            
            cursor.execute(query, (self.current_emp_id, self.current_action_type, status, missing_items))
            conn.commit()
            conn.close()
            print(f"✅ บันทึก DB สำเร็จ -> รหัส: {self.current_emp_id} | รายการ: {self.current_action_type} | สถานะ: {status}")
            
        except mysql.connector.Error as err:
            print(f"Database Error: {err}")

    # --- ฟังก์ชันปิดจบกระบวนการ (อัปเดตให้รับค่าสถานะด้วย) ---
    def finish_ppe_inspection(self, status="FAIL", missing_items=""):
        # 1. บันทึกลง DB ก่อนรีเซ็ตค่า
        if self.current_emp_id:
            self.save_log_to_db(status, missing_items)
            
        # 2. เปลี่ยนแค่สถานะ เพื่อส่งสัญญาณให้ Thread กล้องหยุดทำงาน
        self.is_camera_running = False
        self.ppe_start_time = None
        self.last_person_seen_time = None
        
        # ❌ ลบส่วนนี้ออก (ลบ 3 บรรทัดนี้ออกไปเลยครับ)
        # if self.cap is not None:
        #     self.cap.release()
        #     self.cap = None
            
        self.current_frame = None
        self.video_label.configure(image='')
            
        # 3. ลบไฟล์สื่อสาร
        if os.path.exists("current_scan.json"):
            os.remove("current_scan.json")
            
        # 4. ล้างค่าในหน่วยความจำ
        self.current_emp_id = None
        self.current_action_type = None
        self.emp_info_label.config(text="รอรับข้อมูลจากด่านสแกนหน้า...", fg="gray")
        
        if status == "PASS":
            self.result_label.config(text="✅ การแต่งกายผ่านเกณฑ์ บันทึกข้อมูลสำเร็จ!", fg="green")

    def simulate_pass(self):
        if self.is_camera_running:
            print("ผู้ทดสอบกดจำลองว่าแต่งกายผ่าน")
            self.finish_ppe_inspection(status="PASS", missing_items="")

    def manual_reset(self):
        if self.is_camera_running:
            print("แอดมินสั่งยกเลิกคิวตรวจชุด...")
            self.result_label.config(text="❌ ถูกยกเลิกโดยผู้ดูแลระบบ", fg="red")
            self.finish_ppe_inspection(status="FAIL", missing_items="ยกเลิกรายการโดยผู้ดูแลระบบ")

    def open_dashboard(self):
        print("กำลังเปิดหน้า Web Dashboard...")
        # สั่งเปิด URL ของ Flask
        webbrowser.open("http://127.0.0.1:5000")

    def get_employee_name(self, emp_id):
        try:
            conn = mysql.connector.connect(**self.db_config)
            cursor = conn.cursor()
            query = "SELECT emp_name FROM employee WHERE emp_id = %s"
            cursor.execute(query, (emp_id,))
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else "ไม่พบชื่อในระบบฐานข้อมูล"
        except mysql.connector.Error as err:
            return "DB Connection Error"

if __name__ == "__main__":
    root = tk.Tk()
    app = PPEInspectorApp(root)
    root.mainloop()

    #ลองใช้งาน git ครั้งแรกงงมาก แต่ก็พยายาม