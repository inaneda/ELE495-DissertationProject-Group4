import cv2
import numpy as np
import onnxruntime as ort
from picamera2 import Picamera2

class ResistorDiodeDetectionONNX:

    def __init__(self, capture_index):
        self.capture_index = capture_index
        self.imgsz = 640
        self.conf_thres = 0.5
        self.iou_thres = 0.45

        self.session = ort.InferenceSession(
            "best.onnx",
            providers=["CPUExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name

        print("ONNX Runtime ready (CPU)")

    def preprocess(self, frame):
        img = cv2.resize(frame, (self.imgsz, self.imgsz))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = img.astype(np.float32) / 255.0
        img = np.transpose(img, (2, 0, 1))[None]
        return img

    def postprocess(self, outputs, orig_shape):
        preds = outputs[0][0]  # (num_boxes, 85)

        boxes = []
        scores = []
        class_ids = []

        h, w = orig_shape

        for pred in preds:
            obj_conf = pred[4]
            class_scores = pred[5:]
            cls_id = np.argmax(class_scores)
            score = obj_conf * class_scores[cls_id]

            if score < self.conf_thres:
                continue

            cx, cy, bw, bh = pred[:4]

            x1 = int((cx - bw / 2) * w / self.imgsz)
            y1 = int((cy - bh / 2) * h / self.imgsz)
            x2 = int((cx + bw / 2) * w / self.imgsz)
            y2 = int((cy + bh / 2) * h / self.imgsz)

            boxes.append([x1, y1, x2, y2])
            scores.append(float(score))
            class_ids.append(int(cls_id))

        return boxes, scores, class_ids

    def box_center(self, box):
        x1, y1, x2, y2 = box
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    def euclidean_distance(self, p1, p2):
        return np.linalg.norm(np.array(p1) - np.array(p2))

    def compute_iou(self, boxA, boxB):
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])

        inter = max(0, xB - xA) * max(0, yB - yA)
        areaA = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
        areaB = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
        union = areaA + areaB - inter

        return inter / union if union > 0 else 0.0

    def score_targets(self, target_areas, detected_boxes):
        results = []

        for target in target_areas:
            target_center = self.box_center(target)
            min_dist = float("inf")
            closest_box = None

            for box in detected_boxes:
                dist = self.euclidean_distance(
                    target_center, self.box_center(box)
                )
                if dist < min_dist:
                    min_dist = dist
                    closest_box = box

            iou = self.compute_iou(target, closest_box) if closest_box else 0.0

            results.append({
                "target_box": target,
                "closest_box": closest_box,
                "distance": min_dist,
                "iou_score": iou
            })

        return results

    def __call__(self):
        picam2 = Picamera2()
        picam2.configure(picam2.create_preview_configuration(main={"format":"BGR888", "size":(640,640)}))
        picam2.start()

        while True:
            frame = picam2.capture_array()
            inp = self.preprocess(frame)
            outputs = self.session.run(None, {self.input_name: inp})

            boxes, scores, class_ids = self.postprocess(outputs, frame.shape[:2])

            for box in boxes:
                cv2.rectangle(frame, box[:2], box[2:], (0, 255, 0), 2)

            target_areas = [
                [50, 50, 150, 150],
                [200, 50, 300, 150],
                [50, 200, 150, 300],
                [200, 200, 300, 300]
            ]

            if boxes:
                scores_iou = self.score_targets(target_areas, boxes)
                for i, s in enumerate(scores_iou):
                    print(f"Hedef {i}: IoU = {s['iou_score']:.3f}")

            cv2.imshow("Resistor-Diode Detection (ONNX)", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        cap.release()
        cv2.destroyAllWindows()


detector = ResistorDiodeDetectionONNX(0)
detector()
