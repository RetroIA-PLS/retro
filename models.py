"""Definición de modelos de datos principales."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Nivel:
    """Nivel de desempeño en una rúbrica."""
    nombre: str
    descripcion: str


@dataclass
class Criterio:
    """Criterio a evaluar que contiene múltiples niveles."""
    nombre: str
    niveles: list[Nivel] = field(default_factory=list)


@dataclass
class Rubrica:
    """Rúbrica completa con sus criterios."""
    id: int | None = None
    nombre: str = ""
    contenido: str = ""
    criterios: list[Criterio] = field(default_factory=list)


@dataclass
class Recurso:
    """Recurso educativo del catálogo global."""
    titulo: str
    tipo: str
    url: str
    descripcion: str
    id: int | None = None


@dataclass
class Frase:
    """Frase célebre independiente."""
    texto: str
    autor: str
    id: int | None = None


@dataclass
class Actividad:
    """Actividad que consolida rúbrica, frase y recursos."""
    id: int | None = None
    nombre: str = ""
    proposito: str = ""
    instrucciones: str = ""
    rubrica: Rubrica | None = None
    frase: Frase | None = None
    recursos: list[Recurso] = field(default_factory=list)


@dataclass
class EjemploRetroalimentacion:
    """Estructura obsoleta (se mantiene por compatibilidad)."""
    nombre: str
    contenido: str
    id: int | None = None


@dataclass
class Retroalimentacion:
    """Registro histórico de retroalimentación generada."""
    estudiante: str
    actividad: str
    texto: str
    modelo: str
    calificacion: float
    criterios: dict[str, Any]
    observaciones: str
    prompt: str
    temperatura: float
    id: int | None = None
