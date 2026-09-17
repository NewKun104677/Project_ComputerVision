import subprocess
import sys

print("กำลังเริ่มต้นระบบ Smart Factory Access Control...")

# ใช้ subprocess.Popen เพื่อเปิดไฟล์แบบคู่ขนาน (ไม่รอให้ไฟล์แรกปิด)
# sys.executable คือการดึงตัวรัน Python ในเครื่องมาใช้ให้ถูกต้อง
process1 = subprocess.Popen([sys.executable, "gui_face.py"])
process2 = subprocess.Popen([sys.executable, "gui_ppe.py"])
process_web = subprocess.Popen([sys.executable, "app.py"])

print("เปิดระบบเรียบร้อยแล้ว ทั้ง 2 หน้าต่างกำลังทำงาน!")

# ทำให้ไฟล์นี้รอจนกว่าเราจะปิดหน้าต่าง GUI ทั้งสองอัน
process1.wait()
process2.wait()
process_web.wait()