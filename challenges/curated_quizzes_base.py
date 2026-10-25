"""Helpers shared by the curated quiz data modules."""


def q(text, correct, wrong_1, wrong_2, wrong_3, explanation):
    """Build a question; the correct answer is authored first and positioned by `place`."""
    return {
        "text": text,
        "correct": correct,
        "wrong": [wrong_1, wrong_2, wrong_3],
        "explanation": explanation,
    }


def to_payload(title: str, questions: tuple) -> dict:
    """Return a quiz payload; the correct choice rotates across positions 0..3."""
    items = []
    for number, item in enumerate(questions):
        index = number % 4
        choices = list(item["wrong"])
        choices.insert(index, item["correct"])
        items.append(
            {
                "text": item["text"],
                "choices": choices,
                "correct_index": index,
                "explanation": item["explanation"],
            }
        )
    return {"title": title, "questions": items}
