from flask import Flask, render_template, request  # <-- เพิ่ม request ตรงนี้
import mysql.connector

app = Flask(__name__)

db_config = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "cleanroom_db"
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

@app.route('/')
def dashboard():
    # --- รับค่าคำค้นหา และ ค่าตัวกรองสถานะ ---
    search_query = request.args.get('q', '') 
    status_filter = request.args.get('status', '') 

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cleanup_query = "DELETE FROM entry_logs WHERE timestamp < NOW() - INTERVAL 3 MONTH"
        cursor.execute(cleanup_query)
        conn.commit()
    except Exception as e:
        print(f"เกิดข้อผิดพลาดในการลบข้อมูลเก่า: {e}")
    
    # --- เทคนิคประกอบร่าง SQL (Dynamic Query) ---
    # เริ่มต้นด้วยเงื่อนไข 1=1 เพื่อให้เราเติม AND ต่อท้ายได้เรื่อยๆ
    query = """
        SELECT e.emp_id, e.emp_name, e.department, 
               l.action_type, l.status, l.missing_items, l.timestamp 
        FROM entry_logs l
        JOIN employee e ON l.emp_id = e.emp_id
        WHERE 1=1 
    """
    params = []

    # 1. ถ้ามีการพิมพ์ค้นหา
    if search_query:
        query += " AND (e.emp_id LIKE %s OR e.emp_name LIKE %s)"
        like_pattern = f"%{search_query}%"
        params.extend([like_pattern, like_pattern])
        
    # 2. ถ้ามีการเลือกตัวกรองสถานะ (PASS หรือ FAIL)
    if status_filter in ['PASS', 'FAIL']:
        query += " AND l.status = %s"
        params.append(status_filter)

    # จัดเรียงจากเวลาล่าสุดไปเก่าสุด
    query += " ORDER BY l.timestamp DESC"
    
    # รันคำสั่ง SQL
    cursor.execute(query, tuple(params))
    logs = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    # ส่งตัวแปรกลับไปที่หน้าเว็บ
    return render_template('index.html', logs=logs, search_query=search_query, status_filter=status_filter)

if __name__ == '__main__':
    print("เริ่มต้นเซิร์ฟเวอร์ Web Dashboard ที่ http://127.0.0.1:5000")
    app.run(debug=True, port=5000)