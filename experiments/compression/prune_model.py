import gzip, shutil, os, time, tempfile, torch
import torch.nn.utils.prune as prune
from common import *

def remove_file(path):
    for _ in range(10):
        try:
            os.remove(path)
            return
        except (PermissionError, FileNotFoundError):
            time.sleep(1)

def gzip_size_mb(model):
    tmp = tempfile.gettempdir()
    raw = os.path.join(tmp, "prune_tmp.pt")
    gz = raw + ".gz"
    torch.save(model.state_dict(), raw)
    with open(raw, "rb") as f, gzip.open(gz, "wb", compresslevel=1) as g:
        shutil.copyfileobj(f, g)
    s = os.path.getsize(gz) / 1e6
    remove_file(raw)
    remove_file(gz)
    return round(s, 1)

for amount in (0.3, 0.5):
    tok, model = load()
    linears = [m for m in model.model.layers.modules()
               if isinstance(m, torch.nn.Linear)]
    for m in linears:
        prune.l1_unstructured(m, "weight", amount=amount)
        prune.remove(m, "weight")
    zeros = sum((m.weight == 0).sum().item() for m in linears)
    total = sum(m.weight.numel() for m in linears)
    result = {
        "sparsity_%": round(100 * zeros / total, 1),
        "size_mb": size_mb(model),
        "size_gzip_mb": gzip_size_mb(model),
        "perplexity": perplexity(model, tok),
        "latency_s": latency(model, tok),
    }
    print(amount, result)
    save_result(f"pruning_{int(amount * 100)}", result)