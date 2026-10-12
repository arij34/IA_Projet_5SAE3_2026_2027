from common import *

tok, model = load()
params = sum(p.numel() for p in model.parameters())
result = {
    "params_millions": round(params / 1e6, 1),
    "size_mb": size_mb(model),
    "perplexity": perplexity(model, tok),
    "latency_s": latency(model, tok),
}
print(result)
save_result("baseline", result)