"""Validateurs des fichiers privés du module users."""

from typing import Any

from django.core.exceptions import ValidationError


MAX_CV_SIZE = 5 * 1024 * 1024


def validate_cv_file(value: Any) -> None:
    """Valide l'extension, la taille et la signature PDF d'un CV."""
    name = getattr(value, "name", "")
    if not name.lower().endswith(".pdf"):
        raise ValidationError("Le CV doit être un fichier PDF.")
    if value.size > MAX_CV_SIZE:
        raise ValidationError("La taille du CV ne doit pas dépasser 5 Mo.")

    file_object = value.file
    current_position = file_object.tell()
    file_object.seek(0)
    signature = file_object.read(5)
    file_object.seek(0)
    if signature != b"%PDF-":
        raise ValidationError("Le contenu du fichier n'est pas un PDF valide.")
    if current_position:
        file_object.seek(current_position)
