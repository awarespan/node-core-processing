import cv2
import time
from node_runtime.detection.visual.detector import VisualDetector
from node_runtime.processing.threat_assessment import ThreatAssessor

det = VisualDetector(model_path='yolov8n_best_weapon.pt', imgsz=640, confidence=0.45)
frame = cv2.imread('tests/fixtures/knife_test.jpg')
t0 = time.time()
annotated, detections = det.infer(frame)
t1 = time.time()
print('LATENCY_MS:', round((t1-t0)*1000, 2))
print('DETECTIONS_COUNT:', len(detections))
for d in detections:
    print('  DETECTED:', d.label, 'CONF:', round(d.confidence, 4), 'BOX:', d.bbox)
assessor = ThreatAssessor()
assessment = assessor.evaluate(detections)
print('ASSESSMENT_TIER:', assessment.tier)
print('ASSESSMENT_LABELS:', assessment.labels)
print('ASSESSMENT_CONF:', round(assessment.max_confidence, 4))
