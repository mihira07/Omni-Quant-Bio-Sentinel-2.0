from __future__ import annotations

import time
from pathlib import Path

import cv2
import dlib
import numpy as np
from django.conf import settings


class BiometricEngine:

    def __init__(self):

        self.detector = dlib.get_frontal_face_detector()

        predictor_path = (
            Path(settings.BASE_DIR)
            / "shape_predictor_68_face_landmarks.dat"
        )

        if not predictor_path.exists():
            raise FileNotFoundError(
                f"Missing face landmark model: {predictor_path}"
            )

        self.predictor = dlib.shape_predictor(
            str(predictor_path)
        )

        # Liveness state
        self.phase = "WAIT_FACE"

        self.baseline_yaw = None

        self.no_face_count = 0

        self.last_seen = 0.0

        self.liveness_verified = False

        # Number of consecutive missing frames before reset
        self.no_face_reset_frames = 3

        # Required head movement in degrees
        self.yaw_threshold = 12.0

    # -----------------------------------------------------
    # HEAD POSE
    # -----------------------------------------------------

    def estimate_yaw(
        self,
        gray_frame,
        face,
    ):

        landmarks = self.predictor(
            gray_frame,
            face,
        )

        points_2d = np.array(
            [
                (
                    landmarks.part(30).x,
                    landmarks.part(30).y,
                ),  # nose
                (
                    landmarks.part(8).x,
                    landmarks.part(8).y,
                ),  # chin
                (
                    landmarks.part(36).x,
                    landmarks.part(36).y,
                ),  # left eye
                (
                    landmarks.part(45).x,
                    landmarks.part(45).y,
                ),  # right eye
                (
                    landmarks.part(48).x,
                    landmarks.part(48).y,
                ),  # left mouth
                (
                    landmarks.part(54).x,
                    landmarks.part(54).y,
                ),  # right mouth
            ],
            dtype=np.float64,
        )

        # Generic 3D facial model.
        points_3d = np.array(
            [
                (0.0, 0.0, 0.0),          # nose
                (0.0, -330.0, -65.0),     # chin
                (-225.0, 170.0, -135.0),  # left eye
                (225.0, 170.0, -135.0),   # right eye
                (-150.0, -150.0, -125.0), # left mouth
                (150.0, -150.0, -125.0),  # right mouth
            ],
            dtype=np.float64,
        )

        height, width = gray_frame.shape[:2]

        focal_length = width

        camera_matrix = np.array(
            [
                [
                    focal_length,
                    0,
                    width / 2,
                ],
                [
                    0,
                    focal_length,
                    height / 2,
                ],
                [
                    0,
                    0,
                    1,
                ],
            ],
            dtype=np.float64,
        )

        dist_coeffs = np.zeros(
            (4, 1)
        )

        success, rotation_vector, translation_vector = (
            cv2.solvePnP(
                points_3d,
                points_2d,
                camera_matrix,
                dist_coeffs,
                flags=cv2.SOLVEPNP_ITERATIVE,
            )
        )

        if not success:
            return None

        rotation_matrix, _ = cv2.Rodrigues(
            rotation_vector
        )

        sy = np.sqrt(
            rotation_matrix[0, 0] ** 2
            + rotation_matrix[1, 0] ** 2
        )

        singular = sy < 1e-6

        if not singular:

            x_angle = np.arctan2(
                rotation_matrix[2, 1],
                rotation_matrix[2, 2],
            )

            y_angle = np.arctan2(
                -rotation_matrix[2, 0],
                sy,
            )

            z_angle = np.arctan2(
                rotation_matrix[1, 0],
                rotation_matrix[0, 0],
            )

        else:

            x_angle = np.arctan2(
                -rotation_matrix[1, 2],
                rotation_matrix[1, 1],
            )

            y_angle = np.arctan2(
                -rotation_matrix[2, 0],
                sy,
            )

            z_angle = 0

        yaw = np.degrees(
            y_angle
        )

        return float(yaw)

    # -----------------------------------------------------
    # FACE TELEMETRY + LIVENESS
    # -----------------------------------------------------

    def get_face_telemetry(
        self,
        frame,
    ):

        if frame is None or frame.size == 0:

            return {
                "face_present": False,
                "human_verified": False,
                "status": "NO_FRAME",
                "challenge": "NO_FRAME",
                "yaw": None,
                "bbox": None,
                "face_ratio": 0.0,
            }

        gray = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2GRAY,
        )

        # Improve low-light frames.
        clahe = cv2.createCLAHE(
            clipLimit=2.0,
            tileGridSize=(8, 8),
        )

        gray = clahe.apply(gray)

        faces = self.detector(
            gray,
            2,
        )

        if not faces:

            self.no_face_count += 1

            if (
                self.no_face_count
                >= self.no_face_reset_frames
            ):

                self.phase = "WAIT_FACE"
                self.baseline_yaw = None
                self.liveness_verified = False

            return {
                "face_present": False,
                "human_verified": False,
                "status": "NO_FACE",
                "challenge": "NO_FACE",
                "yaw": None,
                "bbox": None,
                "face_ratio": 0.0,
            }

        self.no_face_count = 0
        self.last_seen = time.time()

        # Use the largest detected face.
        face = max(
            faces,
            key=lambda f:
                f.width() * f.height(),
        )

        x = max(
            0,
            face.left(),
        )

        y = max(
            0,
            face.top(),
        )

        w = min(
            face.width(),
            frame.shape[1] - x,
        )

        h = min(
            face.height(),
            frame.shape[0] - y,
        )

        frame_area = (
            frame.shape[0]
            * frame.shape[1]
        )

        face_area = w * h

        face_ratio = (
            face_area / frame_area
            if frame_area
            else 0.0
        )

        # Ignore extremely tiny detections.
        if face_ratio < 0.015:

            return {
                "face_present": False,
                "human_verified": False,
                "status": "FACE_TOO_SMALL",
                "challenge": "MOVE_CLOSER",
                "yaw": None,
                "bbox": [
                    x,
                    y,
                    w,
                    h,
                ],
                "face_ratio": round(
                    face_ratio,
                    4,
                ),
            }

        # Estimate head yaw.
        yaw = self.estimate_yaw(
            gray,
            face,
        )

        if yaw is None:

            return {
                "face_present": False,
                "human_verified": False,
                "status": "POSE_UNAVAILABLE",
                "challenge": "HOLD_STEADY",
                "yaw": None,
                "bbox": [
                    x,
                    y,
                    w,
                    h,
                ],
                "face_ratio": round(
                    face_ratio,
                    4,
                ),
            }

        # -------------------------------------------------
        # FIRST FACE -> CALIBRATE
        # -------------------------------------------------

        if self.phase == "WAIT_FACE":

            self.baseline_yaw = yaw

            self.phase = "MOVE_LEFT"

            return {
                "face_present": False,
                "human_verified": False,
                "status": "MOVE_LEFT",
                "challenge": "TURN_HEAD_LEFT",
                "yaw": round(
                    yaw,
                    2,
                ),
                "baseline_yaw": round(
                    self.baseline_yaw,
                    2,
                ),
                "bbox": [
                    x,
                    y,
                    w,
                    h,
                ],
                "face_ratio": round(
                    face_ratio,
                    4,
                ),
            }

        # -------------------------------------------------
        # LEFT CHALLENGE
        # -------------------------------------------------

        if self.phase == "MOVE_LEFT":

            if (
                yaw
                <= self.baseline_yaw
                - self.yaw_threshold
            ):

                self.phase = "MOVE_RIGHT"

                return {
                    "face_present": False,
                    "human_verified": False,
                    "status": "MOVE_RIGHT",
                    "challenge": "TURN_HEAD_RIGHT",
                    "yaw": round(
                        yaw,
                        2,
                    ),
                    "baseline_yaw": round(
                        self.baseline_yaw,
                        2,
                    ),
                    "bbox": [
                        x,
                        y,
                        w,
                        h,
                    ],
                    "face_ratio": round(
                        face_ratio,
                        4,
                    ),
                }

            return {
                "face_present": False,
                "human_verified": False,
                "status": "MOVE_LEFT",
                "challenge": "TURN_HEAD_LEFT",
                "yaw": round(
                    yaw,
                    2,
                ),
                "baseline_yaw": round(
                    self.baseline_yaw,
                    2,
                ),
                "bbox": [
                    x,
                    y,
                    w,
                    h,
                ],
                "face_ratio": round(
                    face_ratio,
                    4,
                ),
            }

        # -------------------------------------------------
        # RIGHT CHALLENGE
        # -------------------------------------------------

        if self.phase == "MOVE_RIGHT":

            if (
                yaw
                >= self.baseline_yaw
                + self.yaw_threshold
            ):

                self.phase = "VERIFIED"

                self.liveness_verified = True

                return {
                    "face_present": True,
                    "human_verified": True,
                    "status": "LIVE_PRESENT",
                    "challenge": "VERIFIED",
                    "yaw": round(
                        yaw,
                        2,
                    ),
                    "baseline_yaw": round(
                        self.baseline_yaw,
                        2,
                    ),
                    "bbox": [
                        x,
                        y,
                        w,
                        h,
                    ],
                    "face_ratio": round(
                        face_ratio,
                        4,
                    ),
                }

            return {
                "face_present": False,
                "human_verified": False,
                "status": "MOVE_RIGHT",
                "challenge": "TURN_HEAD_RIGHT",
                "yaw": round(
                    yaw,
                    2,
                ),
                "baseline_yaw": round(
                    self.baseline_yaw,
                    2,
                ),
                "bbox": [
                    x,
                    y,
                    w,
                    h,
                ],
                "face_ratio": round(
                    face_ratio,
                    4,
                ),
            }

        # -------------------------------------------------
        # VERIFIED
        # -------------------------------------------------

        if self.phase == "VERIFIED":

            return {
                "face_present": True,
                "human_verified": True,
                "status": "LIVE_PRESENT",
                "challenge": "VERIFIED",
                "yaw": round(
                    yaw,
                    2,
                ),
                "baseline_yaw": round(
                    self.baseline_yaw,
                    2,
                ),
                "bbox": [
                    x,
                    y,
                    w,
                    h,
                ],
                "face_ratio": round(
                    face_ratio,
                    4,
                ),
            }

        # Safety fallback.
        self.phase = "WAIT_FACE"
        self.baseline_yaw = None
        self.liveness_verified = False

        return {
            "face_present": False,
            "human_verified": False,
            "status": "RESET",
            "challenge": "RETRY",
            "yaw": round(
                yaw,
                2,
            ),
            "bbox": [
                x,
                y,
                w,
                h,
            ],
            "face_ratio": round(
                face_ratio,
                4,
            ),
        }


engine = BiometricEngine()