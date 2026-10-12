import torch
import transformers

print("torch", torch.__version__, "| transformers", transformers.__version__)
print("CUDA disponible :", torch.cuda.is_available())