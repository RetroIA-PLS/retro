# 🌟 RetroIA

![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-App-FF4B4B?logo=streamlit&logoColor=white)
![OpenRouter](https://img.shields.io/badge/IA-OpenRouter-7C3AED)
![Estado](https://img.shields.io/badge/Estado-Activo-22C55E)

## Generador inteligente de retroalimentaciones formativas con IA

**RetroIA** transforma criterios, rúbricas y observaciones docentes en retroalimentaciones claras, accionables y consistentes.
Diseñada para ahorrar tiempo, mejorar la calidad del feedback y mantener trazabilidad completa del proceso de evaluación.

---

## 📚 Tabla de contenidos

- [🚀 Valor del producto](#valor-del-producto)
- [✨ Características principales](#caracteristicas-principales)
- [🖼️ Captura del producto](#captura-del-producto)
- [🧭 Flujo de uso con ejemplos](#flujo-de-uso-con-ejemplos)
- [⚙️ Instalación rápida](#instalacion-rapida)
- [🔐 Variables de entorno](#variables-de-entorno)
- [☁️ Despliegue](#despliegue)
  - [Streamlit Cloud](#streamlit-cloud)
  - [Heroku](#heroku)
- [🧩 Estructura del proyecto](#estructura-del-proyecto)

---

<a id="valor-del-producto"></a>
## 🚀 Valor del producto

- **Reduce tiempo operativo** al generar retroalimentación en segundos.
- **Estandariza calidad** con rúbricas, directrices y ejemplos reutilizables.
- **Mantiene evidencia** gracias al historial y exportación de resultados.
- **Escala fácilmente** con arquitectura modular en Python + Streamlit.

---

<a id="caracteristicas-principales"></a>
## ✨ Características principales

- Generación de retroalimentaciones con IA a partir de actividad, criterios y observaciones.
- Configuración de actividades, rúbricas, recursos y directrices globales.
- Vista previa del prompt y parámetros de generación (modelo, temperatura, tokens).
- Historial con exportación a **TXT, DOCX, PDF y JSON**.
- Procesamiento individual y por lote.
- Soporte de persistencia local (SQLite) y opción remota con Turso/LibSQL.

---

<a id="captura-del-producto"></a>
## 🖼️ Captura del producto

> 📸 **Placeholder de screenshot**
>
> Actualmente no hay una captura oficial incluida en el repositorio. Para agregar una imagen de estilo landing:
>
> 1. Guarda la captura en `assets/retroia-screenshot.png`.
> 2. Reemplaza este bloque por:
>
> ```markdown
> ![Vista principal de RetroIA](assets/retroia-screenshot.png)
> ```
>
> Recomendación visual: resolución aproximada **1600x900** (modo claro), mostrando la vista de generación de retroalimentación.

---

<a id="flujo-de-uso-con-ejemplos"></a>
## 🧭 Flujo de uso con ejemplos

### 1) Crear una actividad
Ejemplo: **"Foro de integración M11"** con propósito, instrucciones y grupo.

### 2) Definir rúbrica
Asocia criterios (p. ej. claridad argumentativa, evidencia, redacción) y niveles de desempeño con puntaje.

### 3) Generar retroalimentación
Selecciona estudiante, captura criterios evaluados y añade observaciones. RetroIA construye el prompt y genera feedback con IA.

### 4) Exportar y reutilizar
Descarga el resultado en **TXT/DOCX/PDF/JSON** o úsalo en formato HTML compacto para Moodle.

### 5) Procesar en lote (opcional)
Agrega varios estudiantes a cola y ejecuta generación masiva para acelerar el cierre de evaluaciones.

---

<a id="instalacion-rapida"></a>
## ⚙️ Instalación rápida

### 1) Clona el repositorio

```bash
git clone https://github.com/HaggiTlahuisca/retroia.git
cd retroia
```

### 2) Crea y activa entorno virtual

**Windows**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3) Instala dependencias

```bash
pip install -r requirements.txt
```

### 4) Ejecuta la app

```bash
streamlit run app.py
```

---

<a id="variables-de-entorno"></a>
## 🔐 Variables de entorno

Puedes definirlas en `.env` para desarrollo local.

| Variable | Requerida | Descripción |
|---|---|---|
| `OPENROUTER_API_KEY` | Sí (para generación IA) | Clave de API usada por el cliente de IA. |
| `TURSO_DATABASE_URL` | No | URL de base remota Turso (LibSQL). |
| `TURSO_AUTH_TOKEN` | No | Token de autenticación para Turso. |
| `TELEGRAM_TOKEN` | Solo si usas bot | Token del bot de Telegram (`telegram_bot.py`). |
| `PORT` | En PaaS | Puerto asignado por plataforma (Heroku/hosting). |

Ejemplo mínimo:

```env
OPENROUTER_API_KEY=tu_clave_aqui
```

---

<a id="despliegue"></a>
## ☁️ Despliegue

### Streamlit Cloud

1. Conecta el repositorio en Streamlit Cloud.
2. Configura `app.py` como archivo principal.
3. Define Python **3.11**.
4. Agrega `OPENROUTER_API_KEY` en **Secrets**.
5. (Opcional) Agrega `TURSO_DATABASE_URL` y `TURSO_AUTH_TOKEN` para persistencia remota.

**Caveat importante:** si usas SQLite local (`retroalimentaciones.db`) en hosting efímero, la información puede perderse entre reinicios. Para datos persistentes, usa Turso/LibSQL.

### Heroku

Este proyecto ya incluye `Procfile`:

- `web`: `streamlit run app.py --server.port=$PORT --server.address=0.0.0.0`
- `worker`: `python telegram_bot.py`

Pasos sugeridos:

1. Crea app y conecta el repo.
2. Define variables de entorno (`OPENROUTER_API_KEY` y, si aplica, Turso).
3. Si no usarás Telegram, deja el worker en 0 dynos.
4. Despliega normalmente con el pipeline de Heroku.

**Caveat importante:** igual que en Streamlit Cloud, evita depender de SQLite local para persistencia de largo plazo.

---

<a id="estructura-del-proyecto"></a>
## 🧩 Estructura del proyecto

```text
retroia/
├── app.py
├── config.py
├── database.py
├── ia_client.py
├── models.py
├── prompt_builder.py
├── styles.py
├── ui.py
├── ui_components.py
├── utils.py
├── validators.py
├── requirements.txt
├── Procfile
├── retroalimentaciones.db
└── telegram_bot.py
```
