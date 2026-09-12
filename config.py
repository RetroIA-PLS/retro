"""Configuración central del sistema."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
EXPORTS_DIR = BASE_DIR / "exports"
LOGS_DIR = BASE_DIR / "logs"
DB_PATH = BASE_DIR / "retroalimentaciones.db"

APP_TITLE = "Generador inteligente de retroalimentaciones formativas con ayuda de la IA"
APP_ICON = "📝"
APP_LAYOUT = "wide"

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_CHAT_URL = f"{OPENROUTER_BASE_URL}/chat/completions"
OPENROUTER_MODELS_URL = f"{OPENROUTER_BASE_URL}/models"
APP_REFERER = "https://retroalimentaciones.local"
APP_X_TITLE = "Retroalimentaciones formativas IA"

DEFAULT_TEMPERATURE = 0.5
DEFAULT_MAX_TOKENS = 4000
DEFAULT_PROMPT_TOKEN_LIMIT = 240000
REQUEST_TIMEOUT_SECONDS = 900

AI_PROVIDERS = {
    "OpenRouter": "openrouter",
    "OpenAI": "openai",
    "Anthropic": "anthropic",
    "Gemini": "gemini",
    "Ollama": "ollama",
    "LM Studio": "lmstudio",
}

# Modelos separados por categoría (Gratis)
MODELOS_GRATIS = {
    "Nvidia Nemotron 3 Ultra 550B (Gratis)": "Nvidia/nemotron-3-ultra-550b-a55b:free",
    "Cohere: North Mini Code (Gratis)": "cohere/north-mini-code:free",
    "Google Gemma 4 31B IT (Gratis)": "google/gemma-4-31b-it:free",
    "Qwen 3 Next (Gratis)": "qwen/qwen-3-235b-a22b",
}

# Modelos separados por categoría (De pago)
MODELOS_PAGO = {
				"GPT 5.6 Luna Pro": "openai/gpt-5.6-luna-pro", 
    "Mistral Nemo": "mistralai/mistral-nemo",
    "Claude 3 Haiku": "anthropic/claude-3-haiku",
    "GPT 4o Mini": "openai/gpt-4o-mini",
    "GPT 5.6 Luna": "openai/gpt-5.6-luna",
    "Claude 5 Sonnet": "anthropic/claude-5-sonnet",
}

# Combinación global para mantener compatibilidad con el resto del sistema
MODELOS_OPENROUTER = {**MODELOS_GRATIS, **MODELOS_PAGO}

DEFAULT_MODEL_NAME = "GPT 5.6 Luna"
DEFAULT_MODEL_ID = MODELOS_OPENROUTER[DEFAULT_MODEL_NAME]

TIPOS_RECURSO = [
    "Video", "PDF", "Artículo", "Enlace", "Documento", "Archivo", "Libro", "Otro"
]

NIVELES_DESEMPENO = [
    "Experto", "Capacitado", "Aceptable", "Aprendiz", "Requiere apoyo", "No evaluable"
]

COLORS = {
    "primary": "#1f77b4",
    "primary_dark": "#0d5298",
    "success": "#2e7d32",
    "warning": "#ed6c02",
    "danger": "#c62828",
    "surface": "#f7f9fb",
    "border": "#d8e2ec",
}

@dataclass(slots=True)
class RuntimeConfig:
    """Configuración seleccionada por el usuario en ejecución."""

    provider: str = "openrouter"
    api_key: str = ""
    model_name: str = DEFAULT_MODEL_NAME
    model_id: str = DEFAULT_MODEL_ID
    temperature: float = DEFAULT_TEMPERATURE
    max_tokens: int = DEFAULT_MAX_TOKENS
