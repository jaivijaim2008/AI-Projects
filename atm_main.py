import serial, cv2
import threading, time
from PIL import Image
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
import sys

from atm_ui import ATM_UI
from face_engine import load_embeddings, face_matches, set_frame

# ── CONFIG ────────────────────────────────────────────────────────────────────
COM_PORT  = 'COM3'
BAUD      = 9600
TEST_MODE = False   # Set True to test UI without Arduino

# Each card UID maps to a person
# faces/<uid>/ folder must contain that person's reference photos
CARDS = {
    '3686F106': {'name': 'jai',  'balance': 498545,'acno': '3453 9876 5342'},
    'F9732707': {'name': 'arun',  'balance': 874587, 'acno': '3481 9384 8734'},
}

cam          = cv2.VideoCapture(0)
latest_frame = None
frame_lock   = threading.Lock()


def camera_loop():
    global latest_frame
    while True:
        ret, frame = cam.read()
        if ret:
            set_frame(frame)
            with frame_lock:
                latest_frame = frame.copy()
        time.sleep(0.03)


def get_frame():
    with frame_lock:
        return latest_frame.copy() if latest_frame is not None else None


preview_on = False


def start_preview(cam_lbl):
    global preview_on
    preview_on = True
    threading.Thread(target=_feed_loop, args=(cam_lbl,), daemon=True).start()

def _feed_loop(cam_lbl):
    global preview_on
    while preview_on:
        f = get_frame()
        if f is not None:
            try:
                rgb = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
                pil = Image.fromarray(rgb)
                cam_lbl.config(image=pil)
            except Exception as e:
                print(f'[CAM] feed error: {e}')
        time.sleep(0.04)


def stop_preview():
    global preview_on
    preview_on = False


def test_loop(ui):
    time.sleep(2)
    uid  = '3686F106'
    user = CARDS[uid]
    while True:
        print('[TEST] Card scan...')
        ui.show_scanning(uid)
        time.sleep(2.5)

        print('[TEST] Face scan...')
        ui.show_face_scan()
        time.sleep(0.3)
        start_preview(ui.cam_lbl)
        time.sleep(3.5)
        stop_preview()

        print('[TEST] Access granted...')
        ui.show_balance(user['name'], user['balance'], user['acno'])
        time.sleep(5)

        print('[TEST] Unknown card...')
        ui.show_scanning('FF FF FF FF')
        time.sleep(2)
        ui.show_error('UNKNOWN CARD', 'Card not registered',
                      'Use your registered bank card')
        time.sleep(3)

        print('[TEST] Face mismatch...')
        ui.show_scanning(uid)
        time.sleep(2)
        ui.show_face_scan()
        time.sleep(0.3)
        start_preview(ui.cam_lbl)
        time.sleep(3.5)
        stop_preview()
        ui.show_error('FACE MISMATCH', 'Face does not match this card',
                      'Security alert — wrong person detected')
        time.sleep(3)

        ui._bridge.sig_welcome.emit()
        time.sleep(4)


def atm_logic(arduino, ui):
    while True:
        try:
            line = arduino.readline().decode('utf-8', errors='ignore').strip()
        except Exception:
            time.sleep(0.1)
            continue

        if not line or not line.startswith('CARD:'):
            continue

        uid = line.replace('CARD:', '').strip().upper()
        print(f'[ATM] Card: "{uid}" (len={len(uid)})')
        print(f'[ATM] Known cards: {list(CARDS.keys())}')

        ui.show_scanning(uid)
        time.sleep(0.5)

        if uid not in CARDS:
            arduino.write(b'FAIL_CARD\n')
            ui.show_error('UNKNOWN CARD', 'Card not registered',
                          'Use your registered bank card')
            time.sleep(4)
        else:
            user = CARDS[uid]
            ui.show_face_scan()
            time.sleep(1.2)
            start_preview(ui.cam_lbl)

            result = face_matches(uid)
            stop_preview()

            owner = user['name'].upper()
            print(f'[ATM] Sending result: {result} to Arduino')

            if result == 'MATCH':
                arduino.write(b'OK\n')
                arduino.flush()
                print(f'[ATM] MATCH — {owner} verified for card {uid}')
                ui.show_balance(user['name'], user['balance'], user['acno'])
                time.sleep(6)
            elif result == 'NO_FACE':
                arduino.write(b'FAIL_FACE\n')
                arduino.flush()
                print(f'[ATM] NO FACE detected for card {uid}')
                ui.show_error(
                    'NO FACE DETECTED',
                    'No face found in camera',
                    'Please look directly at the camera')
                time.sleep(4)
            else:
                arduino.write(b'FAIL_FACE\n')
                arduino.flush()
                print(f'[ATM] MISMATCH — wrong person tried card of {owner}')
                ui.show_error(
                    'ACCESS DENIED',
                    f'This card belongs to {owner}',
                    'Wrong person detected — security alert')
                time.sleep(4)

        ui._bridge.sig_welcome.emit()


if __name__ == '__main__':
    print('[ATM] Pre-loading face embeddings...')
    for uid in CARDS:
        load_embeddings(uid)
        print(f'[ATM] Card UID in use: {uid}')

    threading.Thread(target=camera_loop, daemon=True).start()
    print('[ATM] Camera running')

    app = QApplication(sys.argv)
    ui  = ATM_UI(app)

    if TEST_MODE:
        print('[ATM] *** TEST MODE ***')
        threading.Thread(target=test_loop, args=(ui,), daemon=True).start()
    else:
        try:
            arduino = serial.Serial(COM_PORT, BAUD, timeout=1)
            time.sleep(2)
            print(f'[ATM] Arduino on {COM_PORT}')
        except Exception as e:
            print(f'[ERROR] {e}'); exit(1)
        threading.Thread(target=atm_logic, args=(arduino, ui), daemon=True).start()

    sys.exit(app.exec())