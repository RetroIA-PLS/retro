"""Validaciones de negocio y entrada."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from config import DEFAULT_PROMPT_TOKEN_LIMIT, NIVELES_DESEMPENO


@dataclass(slots=True)
class ValidationResult:
    ok: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        self.ok = False
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)


class Validator:
    """Colección de validadores reutilizables."""

    @staticmethod
    def required(value: str | None, label: str) -> ValidationResult:
        result = ValidationResult()
        if not value or not value.strip():
            result.add_error(f"{label} es obligatorio.")
        return result

    @staticmethod
    def url(value: str | None) -> ValidationResult:
        result = ValidationResult()
        if not value:
            return result
        parsed = urlparse(value.strip())
        if parsed.scheme not in {"http", "https", "file"} or not parsed.netloc and parsed.scheme != "file":
            result.add_error("La URL no es válida. Usa http, https o file.")
        return result

    @staticmethod
    def json_text(value: str | None, label: str = "JSON") -> ValidationResult:
        result = ValidationResult()
        if not value:
            return result
        try:
            json.loads(value)
        except json.JSONDecodeError as exc:
            result.add_error(f"{label} no es JSON válido: {exc.msg}.")
        return result

    @staticmethod
    def duplicate_name(name: str, existing: list[str], current: str | None = None) -> ValidationResult:
        result = ValidationResult()
        normalized = name.strip().lower()
        current_norm = current.strip().lower() if current else None
        if normalized in {item.strip().lower() for item in existing} and normalized != current_norm:
            result.add_error("Ya existe un registro con ese nombre.")
        return result

    @staticmethod
    def rubrica(criterios: dict[str, dict[str, str]] | None) -> ValidationResult:
        result = ValidationResult()
        if not criterios:
            result.add_error("La rúbrica debe contener al menos un criterio.")
            return result
        for criterio, niveles in criterios.items():
            if not criterio.strip():
                result.add_error("Hay un criterio sin nombre.")
            missing = [nivel for nivel in NIVELES_DESEMPENO if nivel not in niveles]
            if missing:
                result.add_warning(f"{criterio}: faltan niveles {', '.join(missing)}.")
        return result

    @staticmethod
    def actividad(nombre: str, descripcion: str, instrucciones: str) -> ValidationResult:
        result = Validator.required(nombre, "El nombre de la actividad")
        if len(descripcion or "") > 4000:
            result.add_warning("La descripción es extensa; puede aumentar el prompt.")
        if len(instrucciones or "") > 6000:
            result.add_warning("Las instrucciones son extensas; revisa la vista previa del prompt.")
        return result

    @staticmethod
    def prompt_length(prompt: str, limit: int = DEFAULT_PROMPT_TOKEN_LIMIT) -> ValidationResult:
        result = ValidationResult()
        estimated_tokens = max(1, len(prompt) // 4)
        if estimated_tokens > limit:
            result.add_error(f"El prompt estimado tiene {estimated_tokens:,} tokens y supera {limit:,}.")
        elif estimated_tokens > limit * 0.8:
            result.add_warning(f"El prompt está cerca del límite: {estimated_tokens:,} tokens estimados.")
        return result

    @staticmethod
    def safe_filename(value: str) -> ValidationResult:
        result = ValidationResult()
        if re.search(r"[<>:/\\|?*]", value):
            result.add_error("El nombre contiene caracteres no permitidos para archivos.")
        return result
