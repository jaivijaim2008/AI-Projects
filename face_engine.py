"""
face_engine.py  –  Uses dlib directly (no face_recognition wrapper needed).
Compatible with Python 3.14+
"""

import os, glob, time, threading
import cv2
import numpy as np
import dlib

# ── dlib models (downloaded automatically if missing) ───────────────────────
MODELS_DIR = os.path.join(os.path.dirname(__file__), 'dlib_models')
os.makedirs(MODELS_DIR, exist_ok=True)

PREDICTOR_PATH  = os.path.join(MODELS_DIR, 'shape_predictor_68_face_landmarks.dat')
RECOGNIZER_PATH = os.path.join(MODELS_DIR, 'dlib_face_recognition_resnet_model_v1.dat')


def _download_models():
    import urllib.request, bz2

    files = {
        PREDICTOR_PATH:  'http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2',
        RECOGNIZER_PATH: 'http://dlib.net/files/dlib_face_recognition_resnet_model_v1.dat.bz2',
    }

    for dest, url in files.items():
        if os.path.exists(dest):
            continue
        bz2_path = dest + '.bz2'
        print(f'[FACE] Downloading {os.path.basename(dest)} ...')
        urllib.request.urlretrieve(url, bz2_path)
        print(f'[FACE] Extracting  {os.path.basename(dest)} ...')
        with bz2.open(bz2_path, 'rb') as src, open(dest, 'wb') as dst:
            dst.write(src.read())
        os.remove(bz2_path)
        print(f'[FACE] ✓ {os.path.basename(dest)} ready')


_download_models()

detector   = dlib.get_frontal_face_detector()
predictor  = dlib.shape_predictor(PREDICTOR_PATH)
recognizer = dlib.face_recognition_model_v1(RECOGNIZER_PATH)

# ── tunables ─────────────────────────────────────────────────────────────────
FACES_DIR           = 'faces'
DISTANCE_THRESHOLD  = 0.48   # lower = stricter  (0.6 is dlib default)
MIN_MATCH_FRACTION  = 0.30   # fraction of face-frames that must match
# ─────────────────────────────────────────────────────────────────────────────

latest_frame = None
frame_lock   = threading.Lock()


def set_frame(frame):
    global latest_frame
    with frame_lock:
        latest_frame = frame.copy()


def get_frame():
    with frame_lock:
        return latest_frame.copy() if latest_frame is not None else None


def _get_embedding(img_bgr):
    """Return 128-d embedding for the largest face in a BGR image, or None."""
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    dets = detector(rgb, 1)
    if len(dets) == 0:
        return None
    det = max(dets, key=lambda d: d.width() * d.height())
    shape = predictor(rgb, det)
    emb   = recognizer.compute_face_descriptor(rgb, shape)
    return np.array(emb)


# ── embedding cache ───────────────────────────────────────────────────────────
_cache = {}


def load_embeddings(uid):
    if uid in _cache:
        return _cache[uid]

    folder = os.path.join(FACES_DIR, uid)
    files  = sorted(
        f for f in glob.glob(os.path.join(folder, '*'))
        if f.lower().endswith(('.jpg', '.jpeg', '.png'))
    )

    embeddings = []
    for path in files:
        img = cv2.imread(path)
        if img is None:
            continue
        emb = _get_embedding(img)
        if emb is not None:
            embeddings.append(emb)
            print(f'[FACE]   ✓ {os.path.basename(path)}')
        else:
            print(f'[FACE]   ✗ {os.path.basename(path)} – no face detected, skipped')

    print(f'[FACE] {len(embeddings)} embedding samples loaded for {uid}')
    _cache[uid] = embeddings
    return embeddings


def face_matches(uid, attempts=25, delay=0.03):
    refs = load_embeddings(uid)

    if not refs:
        print(f'[FACE] No reference samples for {uid} – falling back to any-face check')
        found = any_face(attempts, delay)
        return 'MATCH' if found else 'NO_FACE' 

    face_frames  = 0
    match_frames = 0

    for i in range(attempts):
        frame = get_frame()
        if frame is None:
            time.sleep(delay); continue

        live_emb = _get_embedding(frame)
        if live_emb is None:
            time.sleep(delay); continue

        face_frames += 1

        distances = [np.linalg.norm(ref - live_emb) for ref in refs]
        best_dist = min(distances)

        print(f'[FACE] frame {i+1:2d} | dist={best_dist:.3f} (threshold={DISTANCE_THRESHOLD})')

        if best_dist <= DISTANCE_THRESHOLD:
            match_frames += 1

        remaining = attempts - (i + 1)
        if face_frames >= 5:
            frac = match_frames / face_frames
            max_possible = (match_frames + remaining) / max(face_frames + remaining, 1)
            if frac >= MIN_MATCH_FRACTION and max_possible >= MIN_MATCH_FRACTION:
                print(f'[FACE] Early ACCEPT ({match_frames}/{face_frames} matched)')
                return 'MATCH'
            if max_possible < MIN_MATCH_FRACTION:
                print(f'[FACE] Early REJECT ({match_frames}/{face_frames} matched)')
                return 'MISMATCH' 

        time.sleep(delay)

    if face_frames == 0:
        print('[FACE] No face detected during scan')
        return 'NO_FACE'

    frac = match_frames / face_frames
    print(f'[FACE] Result: {match_frames}/{face_frames} = {frac:.0%} (need {MIN_MATCH_FRACTION:.0%})')
    if frac >= MIN_MATCH_FRACTION:
        return 'MATCH'
    return 'MISMATCH' 


def any_face(attempts=30, delay=0.08):
    for _ in range(attempts):
        f = get_frame()
        if f is not None:
            rgb  = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
            dets = detector(rgb, 1)
            if len(dets) > 0:
                return True
        time.sleep(delay)
    return False