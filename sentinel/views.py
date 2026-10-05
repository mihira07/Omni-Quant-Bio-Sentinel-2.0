import base64
import json

import cv2
import numpy as np

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .biometrics import engine


@csrf_exempt
def analyze_biometrics(request):

    if request.method != "POST":

        return JsonResponse(
            {
                "status": "METHOD_NOT_ALLOWED"
            },
            status=405,
        )

    try:

        payload = json.loads(
            request.body.decode("utf-8")
        )

        image_data = payload.get(
            "image"
        )

        if not image_data:

            return JsonResponse(
                {
                    "face_present": False,
                    "human_verified": False,
                    "status": "NO_IMAGE",
                    "challenge": "NO_IMAGE",
                },
                status=400,
            )

        if "," in image_data:

            image_data = image_data.split(
                ",",
                1,
            )[1]

        raw = base64.b64decode(
            image_data
        )

        image_array = np.frombuffer(
            raw,
            dtype=np.uint8,
        )

        frame = cv2.imdecode(
            image_array,
            cv2.IMREAD_COLOR,
        )

        if frame is None:

            return JsonResponse(
                {
                    "face_present": False,
                    "human_verified": False,
                    "status": "INVALID_IMAGE",
                    "challenge": "INVALID_IMAGE",
                },
                status=400,
            )

        result = engine.get_face_telemetry(
            frame
        )

        print(
            "[BIO-SENTINEL]",
            result,
        )

        return JsonResponse(
            result
        )

    except Exception as exc:

        print(
            "[BIO-SENTINEL ERROR]",
            exc,
        )

        return JsonResponse(
            {
                "face_present": False,
                "human_verified": False,
                "status": "ERROR",
                "challenge": "RETRY",
                "error": str(exc),
            },
            status=500,
        )