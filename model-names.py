from ultralytics import YOLO

model_path = r"C:\Users\saireddy\OneDrive - VALKONTEK EMBEDDED IOT SERVICES PRIVATE LTD\Avis\Tire\tire-model-yolov8s-640X640.pt"

model = YOLO(model_path)
print(model.names)
print(model.task)
print(model.model)