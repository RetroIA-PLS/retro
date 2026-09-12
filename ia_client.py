"""Cliente para comunicación con proveedores de Inteligencia Artificial (OpenRouter)."""

from __future__ import annotations

import json
from typing import Any
import requests

from config import DEFAULT_MAX_TOKENS, DEFAULT_MODEL_ID, DEFAULT_TEMPERATURE


class IAClient:
    def __init__(self, provider: str = "openrouter") -> None:
        self.provider = provider

    def generar(
        self,
        prompt: str,
        api_key: str,
        model_id: str = DEFAULT_MODEL_ID,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> str:
        if not api_key:
            raise ValueError("No se proporcionó la clave de API.")

        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/haggitlahuisca/retroia",
            "X-Title": "RetroIA Formativas",
        }
        payload = {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=90)
        if resp.status_code != 200:
            try:
                err_data = resp.json()
                msg = err_data.get("error", {}).get("message", resp.text)
            except Exception:
                msg = resp.text
            raise RuntimeError(f"Error OpenRouter ({resp.status_code}): {msg}")

        data = resp.json()
        if "choices" not in data or not data["choices"]:
            raise RuntimeError(f"Respuesta inesperada: {json.dumps(data)[:200]}")

        mensaje = data["choices"][0].get("message", {})
        contenido = mensaje.get("content", "")

        # Fallback si el contenido viene en reasoning o texto directo
        if not contenido and "reasoning" in mensaje:
            contenido = mensaje["reasoning"]
        elif not contenido and "text" in mensaje:
            contenido = mensaje["text"]

        if "</think>" in contenido:
            contenido = contenido.split("</think>")[-1].strip()

        if not contenido.strip():
            raise RuntimeError("La respuesta del proveedor no contiene texto utilizable.")

        return contenido.strip()

    def probar_conexion(self, api_key: str, model_id: str) -> tuple[bool, str]:
        try:
            res = self.generar("Di 'OK' en una palabra.", api_key, model_id, max_tokens=10)
            return True, f"Conexión exitosa. Respuesta: {res}"
        except Exception as exc:
            return False, f"Fallo de conexión: {exc}"
