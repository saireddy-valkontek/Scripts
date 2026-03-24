import torch

model_path = r"C:\Users\saireddy\OneDrive - VALKONTEK EMBEDDED IOT SERVICES PRIVATE LTD\Avis\Tire\tire-model-yolov8s-640X640.pt"

model = torch.load(model_path,map_location=torch.device('cpu'),weights_only = False)

print("model type: ", type(model))

print("model architecture: ",model)

print("model attributes and methods: ", dir(model))

if hasattr(model, 'names'):
    print("Class names :",model.names)

dummy_input = torch.randn(1,3,640,640)

try:
    output= model(dummy_input)
    print("output shape: ",type(output))
    print("output shapes: ",output.shape if hasattr(output,'shape') else output)
except Exception as e:
    print("Error running dummy input: ",e)