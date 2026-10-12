from types import SimpleNamespace

from users.ai.profile_analysis import analyze_profile

profil = {"title": "Dev web", "bio": "Je fais des sites.", "skills": ["HTML"], "hourly_rate": 5}
user = SimpleNamespace(username="", first_name="", last_name="")
print(analyze_profile(user, profil))
