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
- [☁️ Uso en la nube (sin instalación)](#uso-en-la-nube)
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

<a id="uso-en-la-nube"></a>
## ☁️ Uso en la nube (sin instalación)

### ✨ Opción más fácil: Streamlit Cloud

Si deseas usar RetroIA **sin instalar nada en tu computadora** y asegurando que todas tus actividades y rúbricas se guarden de forma permanente, debes desplegar tu propia copia del sistema. Solo necesitas configurar tres cuentas gratuitas por única vez:

#### Pasos para empezar:

1. **Clonar el código (GitHub)**
   - Ve a [GitHub](https://github.com/) y crea una cuenta gratuita.
   - Abre el enlace del repositorio de RetroIA que te compartieron.
   - En la esquina superior derecha, haz clic en el botón **"Fork"** (Crear bifurcación). Esto creará una copia exacta del código en tu propia cuenta.

2. **Crear tu Base de Datos permanente (Turso)**
   - *Nota: Streamlit borra los datos cada vez que se reinicia. Turso evitará que pierdas tu información.*
   - Ve a [Turso.tech](https://turso.tech/) y regístrate (puedes usar tu cuenta de GitHub).
   - En tu panel, haz clic en **"Create Database"** y ponle un nombre (ej. `retroia-db`).
   - Una vez creada, entra a la base de datos y copia dos datos importantes en un bloc de notas:
     - **URL de la base de datos:** Cópiala desde el panel principal (empieza con `libsql://...`).
     - **Token de autenticación:** Haz clic en el botón **"Generate Token"** y copia la clave generada.

3. **Obtener tu llave de Inteligencia Artificial (OpenRouter)**
   - Ve a [OpenRouter.ai](https://openrouter.ai/) y regístrate.
   - Dirígete a la sección de **"Keys"** (Claves).
   - Haz clic en **"Create Key"**, ponle un nombre y cópiala. *(Ojo: Solo te la mostrará una vez. Guárdala en tu bloc de notas).*

4. **Desplegar la aplicación (Streamlit Cloud)**
   - Ve a [share.streamlit.io](https://share.streamlit.io/) e inicia sesión vinculando tu cuenta de GitHub.
   - Haz clic en el botón azul **"New app"** (Nueva aplicación).
   - Selecciona el repositorio de RetroIA que "forkeaste" en el paso 1.
   - En el campo *Main file path*, asegúrate de que diga `app.py`.
   - **¡PAUSA CRÍTICA ANTES DE DESPLEGAR!** Haz clic en **"Advanced settings..."** (Configuración avanzada).
   - En el cuadro de texto **Secrets**, pega las tres claves que guardaste, exactamente con este formato:
     ```toml
     OPENROUTER_API_KEY = "pega_aqui_tu_clave_de_openrouter"
     TURSO_DATABASE_URL = "pega_aqui_tu_url_de_turso_que_empieza_con_libsql://"
     TURSO_AUTH_TOKEN = "pega_aqui_el_token_largo_de_turso"
     ```
   - Haz clic en **Save** y luego en **Deploy!** (En un par de minutos, tu aplicación estará viva en internet).

5. **Configuración de tu Perfil**
   - Una vez que abra tu aplicación, ve al menú **"🤖 4. Configuración IA y Perfil"**.
   - Llena tus datos personales (Nombre, Rol, Grupo).
   - Configura tus directrices y da clic en Guardar. ¡Tu RetroIA ya es 100% tuya y está lista para evaluar!

#### Ventajas de este método:
- ✅ **100% Privado y Permanente:** Tu información, rúbricas y alumnos se guardan en tu propia base de datos, nadie más tiene acceso.
- ✅ **Sin instalación:** No necesitas Python ni lidiar con la terminal de comandos.
- ✅ **Acceso universal:** Úsala desde tu PC, Mac, tablet o celular en cualquier lugar.
- ✅ **Cero costo de servidores:** Streamlit, GitHub y Turso ofrecen capas gratuitas más que suficientes para el trabajo de un Asesor Virtual.

---

<a id="instalacion-rapida"></a>
## ⚙️ Instalación rápida

### Para desarrolladores o instalación local:

### 1) Clona el repositorio

```bash
git clone https://github.com/RetroIA-PLS/retro.git
cd retro
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
