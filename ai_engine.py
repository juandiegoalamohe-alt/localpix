import os
import json
import numpy as np
import cv2
from deepface import DeepFace

class AIEngine:
    def __init__(self, model_name="Facenet512", detector_backend="retinaface"):
        """
        model_name options: VGG-Face, Facenet, Facenet512, OpenFace, DeepFace, DeepID, ArcFace, Dlib, SFace
        detector_backend options: opencv, retinaface, mtcnn, ssd, dlib, mediapipe, yolov8
        """
        self.model_name = model_name
        self.detector_backend = detector_backend

    def extract_faces(self, img_path):
        """
        Detects faces and returns embeddings + bounding boxes.
        """
        try:
            # Enforce_detection=False so it doesn't raise error if no face found
            results = DeepFace.represent(
                img_path=img_path, 
                model_name=self.model_name, 
                detector_backend=self.detector_backend,
                enforce_detection=False
            )
            
            extracted = []
            for res in results:
                # results is a list of dicts: {embedding, facial_area, face}
                if res.get('facial_area', {}).get('w', 0) > 0:
                    extracted.append({
                        "embedding": res['embedding'],
                        "box": res['facial_area'] # {x, y, w, h}
                    })
            return extracted
        except Exception as e:
            print(f"AI Engine Error: {e}")
            return []

    def get_similarity(self, v1, v2):
        """
        Calculates cosine similarity (or distance).
        DeepFace usually uses cosine distance.
        """
        # Manual cosine similarity for quick comparison
        v1 = np.array(v1)
        v2 = np.array(v2)
        return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

# Global instance
engine = AIEngine()
