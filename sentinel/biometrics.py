"""Bio-Sentinel face detection and head-turn liveness verification."""

from collections import deque
from pathlib import Path
from statistics import median
from threading import Lock
from time import monotonic

import cv2
import dlib
import numpy as np


class BioSentinelEngine:
    MIN_FACE_RATIO = 0.025
    TURN_THRESHOLD_DEGREES = 9.0
    REQUIRED_STABLE_FRAMES = 2
    BASELINE_FRAMES = 5
    NO_FACE_RESET_SECONDS = 5.0
    CHALLENGE_TIMEOUT_SECONDS = 25.0

    def __init__(self):
        self.model_path = (
            Path(__file__).resolve().parent.parent
            / "shape_predictor_68_face_landmarks.dat"
        )

        self.detector = None
        self.predictor = None
        self._model_error = None

        self._lock = Lock()
        self._reset_challenge()
        self._last_face_time = 0.0

    def _ensure_loaded(self):
        if self.detector is not None and self.predictor is not None:
            return

        if self._model_error is not None:
            raise RuntimeError(self._model_error)

        if not self.model_path.exists():
            self._model_error = (
                "Dlib landmark model not found: "
                f"{self.model_path}"
            )
            raise FileNotFoundError(self._model_error)

        try:
            self.detector = dlib.get_frontal_face_detector()
            self.predictor = dlib.shape_predictor(
                str(self.model_path)
            )
        except Exception as exc:
            self._model_error = (
                f"Unable to load the Bio-Sentinel face model: {exc}"
            )
            raise RuntimeError(self._model_error) from exc

    def _reset_challenge(self):
        self.stage = "CALIBRATING"
        self.baseline_samples = []
        self.baseline_yaw = None
        self.stage_started_at = monotonic()
        self.first_turn_sign = None
        self._stable_move_frames = 0
        self._yaw_history = deque(maxlen=3)

    def reset_challenge(self):
        """Public method to restart the liveness verification."""
        with self._lock:
            self._reset_challenge()
            self._last_face_time = 0.0

    @staticmethod
    def _result(
        face_present=False,
        human_verified=False,
        status="NO_FACE",
        challenge="NO_FACE",
        yaw=None,
        baseline_yaw=None,
        bbox=None,
        face_ratio=0.0,
        ear=0.0,
    ):
        return {
            "face_present": bool(face_present),
            "human_verified": bool(human_verified),
            "status": status,
            "challenge": challenge,
            "yaw": (
                round(float(yaw), 2)
                if yaw is not None
                else None
            ),
            "baseline_yaw": (
                round(float(baseline_yaw), 2)
                if baseline_yaw is not None
                else None
            ),
            "bbox": bbox,
            "face_ratio": round(float(face_ratio), 4),
            "ear": round(float(ear), 4),
        }

    @staticmethod
    def _eye_aspect_ratio(eye_points):
        points = np.asarray(
            eye_points,
            dtype=np.float64,
        )

        horizontal = np.linalg.norm(
            points[0] - points[3]
        )

        if horizontal <= 1e-6:
            return 0.0

        vertical_a = np.linalg.norm(
            points[1] - points[5]
        )
        vertical_b = np.linalg.norm(
            points[2] - points[4]
        )

        return float(
            (vertical_a + vertical_b)
            / (2.0 * horizontal)
        )

    @staticmethod
    def calculate_ear(eye_points):
        return BioSentinelEngine._eye_aspect_ratio(
            eye_points
        )

    def _detect_face(self, gray):
        """Try multiple grayscale enhancements for webcam detection."""
        self._ensure_loaded()

        clahe = cv2.createCLAHE(
            clipLimit=2.2,
            tileGridSize=(8, 8),
        ).apply(gray)

        equalized = cv2.equalizeHist(gray)

        for image in (gray, clahe, equalized):
            rects = self.detector(image, 1)

            if rects:
                return rects, image

        rects = self.detector(clahe, 2)

        if rects:
            return rects, clahe

        return [], clahe

    @staticmethod
    def _estimate_yaw(coords, width, height):
        """Estimate approximate horizontal head rotation from landmarks."""
        image_points = np.array(
            [
                coords[30],
                coords[8],
                coords[36],
                coords[45],
                coords[48],
                coords[54],
            ],
            dtype=np.float64,
        )

        model_points = np.array(
            [
                (0.0, 0.0, 0.0),
                (0.0, -330.0, -65.0),
                (-225.0, 170.0, -135.0),
                (225.0, 170.0, -135.0),
                (-150.0, -150.0, -125.0),
                (150.0, -150.0, -125.0),
            ],
            dtype=np.float64,
        )

        focal_length = float(width)
        center = (
            width / 2.0,
            height / 2.0,
        )

        camera_matrix = np.array(
            [
                [focal_length, 0.0, center[0]],
                [0.0, focal_length, center[1]],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )

        distortion = np.zeros(
            (4, 1),
            dtype=np.float64,
        )

        success, rotation_vector, _ = cv2.solvePnP(
            model_points,
            image_points,
            camera_matrix,
            distortion,
            flags=cv2.SOLVEPNP_ITERATIVE,
        )

        if not success:
            return None

        rotation_matrix, _ = cv2.Rodrigues(
            rotation_vector
        )

        angles = cv2.RQDecomp3x3(
            rotation_matrix
        )[0]

        yaw = float(angles[1])

        if not np.isfinite(yaw):
            return None

        return yaw

    def get_face_telemetry(self, frame):
        if frame is None or getattr(frame, "size", 0) == 0:
            return self._result()

        with self._lock:
            now = monotonic()

            if len(frame.shape) == 3:
                gray = cv2.cvtColor(
                    frame,
                    cv2.COLOR_BGR2GRAY,
                )
            else:
                gray = frame.copy()

            rects, detector_image = self._detect_face(
                gray
            )

            if not rects:
                if (
                    self._last_face_time
                    and now - self._last_face_time
                    > self.NO_FACE_RESET_SECONDS
                ):
                    self._reset_challenge()

                return self._result(
                    face_present=False,
                    human_verified=False,
                    status="NO_FACE",
                    challenge="NO_FACE",
                    baseline_yaw=self.baseline_yaw,
                )

            rect = max(
                rects,
                key=lambda item: (
                    item.width() * item.height()
                ),
            )

            left = max(
                0,
                int(rect.left()),
            )
            top = max(
                0,
                int(rect.top()),
            )
            right = min(
                gray.shape[1] - 1,
                int(rect.right()),
            )
            bottom = min(
                gray.shape[0] - 1,
                int(rect.bottom()),
            )

            face_width = max(
                0,
                right - left,
            )
            face_height = max(
                0,
                bottom - top,
            )

            face_ratio = (
                face_width * face_height
            ) / max(
                1,
                gray.shape[0] * gray.shape[1],
            )

            bbox = [
                left,
                top,
                face_width,
                face_height,
            ]

            self._last_face_time = now

            if (
                face_ratio < self.MIN_FACE_RATIO
                or face_width < 45
                or face_height < 45
            ):
                return self._result(
                    face_present=False,
                    human_verified=False,
                    status="FACE_TOO_SMALL",
                    challenge="MOVE_CLOSER",
                    baseline_yaw=self.baseline_yaw,
                    bbox=bbox,
                    face_ratio=face_ratio,
                )

            shape = self.predictor(
                detector_image,
                rect,
            )

            coords = np.array(
                [
                    [point.x, point.y]
                    for point in shape.parts()
                ],
                dtype=np.float64,
            )

            left_ear = self._eye_aspect_ratio(
                coords[42:48]
            )
            right_ear = self._eye_aspect_ratio(
                coords[36:42]
            )

            ear = float(
                (left_ear + right_ear) / 2.0
            )

            yaw = self._estimate_yaw(
                coords,
                gray.shape[1],
                gray.shape[0],
            )

            if yaw is None:
                return self._result(
                    face_present=True,
                    human_verified=False,
                    status="POSE_UNCERTAIN",
                    challenge="CENTER_FACE",
                    baseline_yaw=self.baseline_yaw,
                    bbox=bbox,
                    face_ratio=face_ratio,
                    ear=ear,
                )

            self._yaw_history.append(yaw)
            smoothed_yaw = float(
                median(self._yaw_history)
            )

            if self.stage == "VERIFIED":
                return self._result(
                    face_present=True,
                    human_verified=True,
                    status="LIVE_PRESENT",
                    challenge="VERIFIED",
                    yaw=smoothed_yaw,
                    baseline_yaw=self.baseline_yaw,
                    bbox=bbox,
                    face_ratio=face_ratio,
                    ear=ear,
                )

            if (
                self.stage in {"MOVE_LEFT", "MOVE_RIGHT"}
                and now - self.stage_started_at
                > self.CHALLENGE_TIMEOUT_SECONDS
            ):
                self._reset_challenge()

            if self.stage == "CALIBRATING":
                self.baseline_samples.append(
                    smoothed_yaw
                )

                if (
                    len(self.baseline_samples)
                    < self.BASELINE_FRAMES
                ):
                    return self._result(
                        face_present=True,
                        status="CALIBRATING",
                        challenge="CENTER_FACE",
                        yaw=smoothed_yaw,
                        bbox=bbox,
                        face_ratio=face_ratio,
                        ear=ear,
                    )

                self.baseline_yaw = float(
                    median(
                        self.baseline_samples[
                            -self.BASELINE_FRAMES:
                        ]
                    )
                )

                self.stage = "MOVE_LEFT"
                self.stage_started_at = now
                self.first_turn_sign = None
                self._stable_move_frames = 0

                return self._result(
                    face_present=True,
                    status="MOVE_LEFT",
                    challenge="TURN_HEAD_LEFT",
                    yaw=smoothed_yaw,
                    baseline_yaw=self.baseline_yaw,
                    bbox=bbox,
                    face_ratio=face_ratio,
                    ear=ear,
                )

            delta = (
                smoothed_yaw
                - float(self.baseline_yaw)
            )

            if self.stage == "MOVE_LEFT":
                # Accept either initial yaw direction to accommodate
                # differences in webcam orientation and mirroring.
                if abs(delta) >= self.TURN_THRESHOLD_DEGREES:
                    self._stable_move_frames += 1
                else:
                    self._stable_move_frames = 0

                if (
                    self._stable_move_frames
                    >= self.REQUIRED_STABLE_FRAMES
                ):
                    self.first_turn_sign = (
                        1 if delta > 0 else -1
                    )

                    self.stage = "MOVE_RIGHT"
                    self.stage_started_at = now
                    self._stable_move_frames = 0

                    return self._result(
                        face_present=True,
                        status="MOVE_RIGHT",
                        challenge="TURN_HEAD_RIGHT",
                        yaw=smoothed_yaw,
                        baseline_yaw=self.baseline_yaw,
                        bbox=bbox,
                        face_ratio=face_ratio,
                        ear=ear,
                    )

                return self._result(
                    face_present=True,
                    status="MOVE_LEFT",
                    challenge="TURN_HEAD_LEFT",
                    yaw=smoothed_yaw,
                    baseline_yaw=self.baseline_yaw,
                    bbox=bbox,
                    face_ratio=face_ratio,
                    ear=ear,
                )

            if self.stage == "MOVE_RIGHT":
                # The second movement must reverse the first movement.
                reversed_direction = (
                    self.first_turn_sign is not None
                    and delta * self.first_turn_sign
                    <= -self.TURN_THRESHOLD_DEGREES
                )

                if reversed_direction:
                    self._stable_move_frames += 1
                else:
                    self._stable_move_frames = 0

                if (
                    self._stable_move_frames
                    >= self.REQUIRED_STABLE_FRAMES
                ):
                    self.stage = "VERIFIED"

                    return self._result(
                        face_present=True,
                        human_verified=True,
                        status="LIVE_PRESENT",
                        challenge="VERIFIED",
                        yaw=smoothed_yaw,
                        baseline_yaw=self.baseline_yaw,
                        bbox=bbox,
                        face_ratio=face_ratio,
                        ear=ear,
                    )

                return self._result(
                    face_present=True,
                    status="MOVE_RIGHT",
                    challenge="TURN_HEAD_RIGHT",
                    yaw=smoothed_yaw,
                    baseline_yaw=self.baseline_yaw,
                    bbox=bbox,
                    face_ratio=face_ratio,
                    ear=ear,
                )

            self._reset_challenge()

            return self._result(
                face_present=True,
                status="CALIBRATING",
                challenge="CENTER_FACE",
                yaw=smoothed_yaw,
                bbox=bbox,
                face_ratio=face_ratio,
                ear=ear,
            )

    def detect_faces(self, frame):
        """Compatibility method for callers using detect_faces()."""
        return self.get_face_telemetry(frame)

    def analyze(self, frame):
        """Compatibility method for callers using analyze()."""
        return self.get_face_telemetry(frame)

    def get_stress_status(self, frame):
        telemetry = self.get_face_telemetry(frame)

        if not telemetry["face_present"]:
            return "NO_FACE"

        if telemetry["ear"] < 0.20:
            return "LOCKDOWN"

        return "STABLE"


# IMPORTANT: sentinel.views imports this object directly.
# Loading the landmark model is deferred until the first camera frame.
engine = BioSentinelEngine()