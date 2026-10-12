import torch
from common import *

tok, model = load()
qmodel = torch.quantization.quantize_dynamic(
    model, {torch.nn.Linear}, dtype=torch.qint8
)
result = {
    "size_mb": size_mb(qmodel),
    "perplexity": perplexity(qmodel, tok),
    "latency_s": latency(qmodel, tok),
}
print(result)
save_result("quantization_int8", result)