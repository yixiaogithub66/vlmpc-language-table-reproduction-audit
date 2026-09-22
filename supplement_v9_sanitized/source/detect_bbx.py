from pathlib import Path

import cv2
import numpy as np
from PIL import Image


CLASSES_DIC = {
    "blue cube": 0,
    "blue moon": 1,
    "yellow pentagon": 2,
    "yellow star": 3,
    "red pentagon": 4,
    "red moon": 5,
    "green cube": 6,
    "green star": 7,
    "end effector": 8,
}
REV_CLASSES_DIC = {value: key for key, value in CLASSES_DIC.items()}


def detect_visible_objects(image_path, model, include_end_effector=True):
    image_path = Path(image_path)
    image = Image.open(image_path)
    results = model(image)
    detections = results.pred[0].cpu().numpy()
    if detections.size == 0:
        return {}

    best_by_class = {}
    for detection in detections:
        class_id = int(detection[5])
        class_name = REV_CLASSES_DIC.get(class_id)
        if class_name is None:
            continue
        if not include_end_effector and class_name == "end effector":
            continue
        if class_id not in best_by_class or detection[4] > best_by_class[class_id][4]:
            best_by_class[class_id] = detection

    visible_objects = {}
    for class_id, detection in best_by_class.items():
        x1, y1, x2, y2 = map(int, detection[:4])
        visible_objects[REV_CLASSES_DIC[class_id]] = {
            "bbox": [[x1, y1], [x2, y2]],
            "confidence": float(detection[4]),
        }
    return visible_objects


def det_bbox(image_path, model, obj_str):
    image_path = Path(image_path)
    visible_objects = detect_visible_objects(image_path=image_path, model=model, include_end_effector=True)
    selected = visible_objects.get(obj_str)
    if selected is None:
        return 0

    image_cv = cv2.cvtColor(np.array(Image.open(image_path)), cv2.COLOR_RGB2BGR)
    x1, y1 = selected["bbox"][0]
    x2, y2 = selected["bbox"][1]
    confidence = selected["confidence"]

    label = f"{obj_str} {confidence:.2f}"
    cv2.rectangle(image_cv, (x1, y1), (x2, y2), (255, 0, 0), 2)
    cv2.putText(image_cv, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
    cv2.imwrite(str(image_path.with_name(f"{image_path.stem}_{obj_str}.jpg")), image_cv)

    return [[x1, y1], [x2, y2]]
