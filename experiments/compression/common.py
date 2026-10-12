import time, os, json, torch
from transformers import AutoTokenizer, AutoModelForCausalLM

MODEL_NAME = os.environ.get("MODEL_NAME", "Qwen/Qwen2.5-0.5B-Instruct")
torch.set_num_threads(4)

TEXTS = [
    "Software engineering is the systematic application of engineering approaches to software development.",
    "A REST API exposes resources through HTTP methods such as GET, POST, PUT and DELETE.",
    "Unit tests verify that each small part of a program behaves as expected.",
    "A good freelancer profile has a clear title, a detailed bio, and a portfolio of past work.",
]
PROMPT = "Give 3 tips to improve a freelancer profile on a marketplace:"

def load():
    tok = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, dtype=torch.float32).eval()
    return tok, model

def size_mb(model):
    import tempfile
    path = os.path.join(tempfile.gettempdir(), "tmp_model.pt")
    torch.save(model.state_dict(), path)
    s = os.path.getsize(path) / 1e6
    for _ in range(10):
        try:
            os.remove(path)
            break
        except PermissionError:
            time.sleep(1)
    return round(s, 1)

@torch.no_grad()
def perplexity(model, tok):
    losses = []
    for t in TEXTS:
        ids = tok(t, return_tensors="pt")
        out = model(**ids, labels=ids["input_ids"])
        losses.append(out.loss.item())
    return round(float(torch.exp(torch.tensor(losses).mean())), 2)

@torch.no_grad()
def latency(model, tok, runs=5, new_tokens=30):
    ids = tok(PROMPT, return_tensors="pt")
    model.generate(**ids, max_new_tokens=5)
    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        model.generate(**ids, max_new_tokens=new_tokens, do_sample=False)
        times.append(time.perf_counter() - t0)
    return round(sum(times) / runs, 2)

def save_result(name, data, file="results.json"):
    res = json.load(open(file)) if os.path.exists(file) else {}
    res[name] = data
    json.dump(res, open(file, "w"), indent=2)