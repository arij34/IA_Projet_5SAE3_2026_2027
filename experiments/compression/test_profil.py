import torch
from common import *

tok, model = load()

profil = """Titre: Développeur web
Bio: Je fais des sites web.
Compétences: HTML, CSS
Tarif horaire: 5 EUR"""

messages = [
    {"role": "system", "content": "You are an expert coach for freelancers. Reply in French."},
    {"role": "user", "content": f"Analyse ce profil freelancer et donne 3 suggestions d'amélioration:\n{profil}"},
]
ids = tok.apply_chat_template(messages, add_generation_prompt=True,
                              return_tensors="pt", return_dict=True)
with torch.no_grad():
    out = model.generate(**ids, max_new_tokens=200, do_sample=False)
print(tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True))