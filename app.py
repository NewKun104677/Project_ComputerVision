import cv2
import time

IP_camera = '192.168.1.108'
url = 'rtsp://admin:p@ssw0rd@' + IP_camera + ':554/cam/realmonitor?channel=1&subtype=0'     # mainstream subtype = 0 , substream subtype = 1
cap = cv2.VideoCapture(url)

#cap = cv2.VideoCapture(1) 
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)       # 1920 x 1080
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

if not cap.isOpened():
    print("Fail to connect camera !!")
    exit()


prev_time = time.time()
fps = 0

while True:
    ret, frame = cap.read()
    if not ret or frame is None:
        print("Camera Stream Disconnect!!")
        time.sleep(0.5)  
        continue
    
    # FPS Calculate (smooth)
    curr_time = time.time()
    fps = (1 / (curr_time - prev_time))
    prev_time = curr_time
    
    # Push FPS to window frame
    cv2.putText(frame, f"FPS: {fps:.2f}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)
    
    cv2.imshow("Video capture", frame)
    
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q') or key == 27:  # q หรือ ESC เพื่อออก
        print("Exit by user")
        break

cap.release()
cv2.destroyAllWindows()