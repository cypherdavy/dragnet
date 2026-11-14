
import cv2
import numpy as np
import queue

def live_viewer_process(frame_queue):
    """
    This function runs in a separate process.
    It gets frames from a queue and displays them in an OpenCV window.
    """
    print("[Viewer] Live Viewer process started.")
    window_name = "Dragnet - Live Desktop Stream"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    while True:
        try:
            
            frame_data = frame_queue.get()

           
            if frame_data is None:
                break
            
            
            frame_array = np.frombuffer(frame_data, dtype=np.uint8)
            frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)

            if frame is not None:
                cv2.imshow(window_name, frame)

            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        except queue.Empty:
            continue 
        except Exception as e:
            print(f"[Viewer Error] {e}")
            break
            
    cv2.destroyAllWindows()
    print("[Viewer] Live Viewer process stopped.")