"""Bot de Telegram para generación de retroalimentaciones alojado en un Worker de Heroku (Modo Polling)."""

from __future__ import annotations

import os
import time
import random
import io
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from dotenv import load_dotenv

from database import DatabaseManager
from prompt_builder import PromptBuilder
from ia_client import IAClient
from models import Retroalimentacion
from utils import docx_bytes, sanitize_filename, get_activity_code, feedback_to_moodle_html, generar_nombre_archivo

# 1. CARGA DE CREDENCIALES
load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TOKEN:
    raise ValueError("No se encontró TELEGRAM_TOKEN en las variables de entorno.")

bot = telebot.TeleBot(TOKEN)
db = DatabaseManager()
ia_client = IAClient("openrouter")

# --- FUNCIÓN DE BITÁCORA (LOGS A BASE DE DATOS) ---
def bot_log(nivel: str, mensaje: str):
    print(f"[{nivel}] {mensaje}")
    try:
        db.add_log(nivel, mensaje)
    except Exception as e:
        print(f"Error escribiendo en BD: {e}")

# 2. LÓGICA DE LA EVALUACIÓN Y CATÁLOGO DE MODELOS
sesiones: dict[int, dict] = {}

NIVELES_NOMBRES = ["Experto", "Capacitado", "Aceptable", "Aprendiz", "Requiere apoyo", "No evaluable"]
NIVELES_CLAVES = ["experto", "capacitado", "aceptable", "aprendiz", "requiere_apoyo", "no_evaluable"]

def obtener_teclado_modelos() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("🎲 Rotación Aleatoria", callback_data="mod_auto"))
    
    modelos = db.get_modelos()
    botones_reales = [
        InlineKeyboardButton(m["nombre"], callback_data=f"mod_{m['id']}")
        for m in modelos
    ]
    if botones_reales:
        markup.add(*botones_reales)
        
    return markup


def obtener_teclado_niveles(prefijo: str) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(row_width=2)
    botones = [
        InlineKeyboardButton(nombre, callback_data=f"{prefijo}_{clave}")
        for nombre, clave in zip(NIVELES_NOMBRES, NIVELES_CLAVES)
    ]
    markup.add(*botones)
    return markup


def obtener_teclado_obs() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("❌ Ninguna", callback_data="obs_ninguna"),
        InlineKeyboardButton("📝 Escribir nota", callback_data="obs_escribir")
    )
    markup.add(
        InlineKeyboardButton("⚠️ Error de Formato", callback_data="obs_formato")
    )
    return markup


def obtener_puntos(actividad_nombre: str, criterio: str, nivel_idx: int) -> float:
    is_foro = "foro de integración" in actividad_nombre.lower()
    if is_foro:
        if criterio == "cog": return [40.0, 34.0, 32.0, 28.0, 24.0, 0.0][nivel_idx]
        else: return [15.0, 14.0, 12.0, 11.0, 9.0, 0.0][nivel_idx]
    else:
        if criterio == "cog": return [40.0, 36.0, 32.0, 28.0, 24.0, 0.0][nivel_idx]
        else: return [20.0, 18.0, 16.0, 14.0, 12.0, 0.0][nivel_idx]


@bot.message_handler(commands=['ayuda'])
def comando_ayuda(message):
    texto_ayuda = (
        "🤖 *Bienvenido al Asistente de Retroalimentación IA*\n\n"
        "Comandos disponibles:\n\n"
        "🔹 /evaluar - Inicia una evaluación individual.\n"
        "🔹 /lote - Inicia el modo de captura masiva en lote.\n"
        "🔹 /cancelar - Cancela la sesión activa y reinicia el bot.\n"
        "🔹 /ayuda - Muestra estas instrucciones."
    )
    bot.send_message(message.chat.id, texto_ayuda, parse_mode="Markdown")


@bot.message_handler(commands=['start', 'evaluar', 'lote'])
def iniciar_evaluacion(message):
    actividades = db.list_activities()
    if not actividades:
        bot.send_message(message.chat.id, "⚠️ No hay actividades configuradas.")
        return

    modo = "batch" if message.text.startswith('/lote') else "individual"
    sesiones[message.chat.id] = {
        "modo": modo,
        "paso": "modelo",
        "criterios": {},
        "total_puntos": 0.0,
        "cola": [],
        "modelo_id": "auto",
        "modelo_nombre": "🎲 Rotación Aleatoria"
    }

    bot_log("INFO", f"Sesión iniciada. Modo: {modo}. Usuario: {message.chat.id}")

    dirs = db.get_all_directrices()
    n_ase = dirs.get("asesor_nombre", "Asesor").split()[0] if dirs.get("asesor_nombre") else "Asesor"

    encabezado = "📦 *Modo Lote activado*\n" if modo == "batch" else f"👋 ¡Hola, {n_ase}!\n"
    bot.send_message(
        message.chat.id,
        f"{encabezado}Selecciona el **modelo de IA** para evaluar:",
        reply_markup=obtener_teclado_modelos(),
        parse_mode="Markdown"
    )


@bot.message_handler(commands=['cancelar'])
def cancelar_evaluacion(message):
    chat_id = message.chat.id
    if chat_id in sesiones:
        del sesiones[chat_id]
        bot_log("INFO", f"Sesión cancelada por el usuario: {chat_id}")
        bot.send_message(chat_id, "🚫 Evaluación cancelada. Escribe /evaluar o /lote para iniciar.")
    else:
        bot.send_message(chat_id, "No hay ninguna evaluación en curso para cancelar.")


@bot.callback_query_handler(func=lambda call: call.data.startswith('mod_'))
def seleccionar_modelo(call):
    chat_id = call.message.chat.id
    mod_id_str = call.data.split('_', 1)[1]
    
    if mod_id_str == "auto":
        sesiones[chat_id]["modelo_id"] = "auto"
        sesiones[chat_id]["modelo_nombre"] = "🎲 Rotación Aleatoria"
        nombre_display = "🎲 Rotación Aleatoria"
    else:
        modelos = db.get_modelos()
        mod = next((m for m in modelos if str(m['id']) == mod_id_str), None)
        if mod:
            sesiones[chat_id]["modelo_id"] = mod["api_id"]
            sesiones[chat_id]["modelo_nombre"] = mod["nombre"]
            nombre_display = mod["nombre"]
        else:
            sesiones[chat_id]["modelo_id"] = "auto"
            sesiones[chat_id]["modelo_nombre"] = "🎲 Rotación Aleatoria"
            nombre_display = "🎲 Rotación Aleatoria"

    sesiones[chat_id]["paso"] = "actividad"

    actividades = db.list_activities()
    markup = InlineKeyboardMarkup(row_width=1)
    for act in actividades:
        markup.add(InlineKeyboardButton(act["nombre"], callback_data=f"act_{act['id']}"))

    bot.edit_message_text(
        f"🤖 Modelo seleccionado: *{nombre_display}*\n\nSelecciona la actividad a evaluar:",
        chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode="Markdown"
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('act_'))
def seleccionar_actividad(call):
    chat_id = call.message.chat.id
    actividad_id = int(call.data.split('_')[1])
    act_obj = db.get_activity(actividad_id)

    if act_obj:
        sesiones[chat_id]["actividad"] = act_obj
        sesiones[chat_id]["paso"] = "nombre"
        bot.edit_message_text(
            f"✅ Actividad: *{act_obj.nombre}*\n\nEscribe el nombre del estudiante:",
            chat_id=chat_id, message_id=call.message.message_id, parse_mode="Markdown"
        )


@bot.message_handler(func=lambda message: sesiones.get(message.chat.id, {}).get("paso") == "nombre")
def recibir_nombre(message):
    chat_id = message.chat.id
    sesiones[chat_id]["estudiante"] = message.text
    sesiones[chat_id]["paso"] = "cognitivo"

    bot.send_message(
        chat_id, "🧠 *Criterio Cognitivo*\nSelecciona el nivel alcanzado:",
        reply_markup=obtener_teclado_niveles("cog"), parse_mode="Markdown"
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('cog_'))
def recibir_cognitivo(call):
    chat_id = call.message.chat.id
    nivel_idx = NIVELES_CLAVES.index(call.data.split('_', 1)[1])
    nivel_nombre = NIVELES_NOMBRES[nivel_idx]

    puntos = obtener_puntos(sesiones[chat_id]["actividad"].nombre, "cog", nivel_idx)

    sesiones[chat_id]["criterios"]["Cognitivo"] = {"nivel": nivel_nombre, "puntos": puntos}
    sesiones[chat_id]["total_puntos"] += puntos
    sesiones[chat_id]["paso"] = "actitudinal"

    bot.edit_message_text(
        "🤝 *Criterio Actitudinal*\nSelecciona el nivel alcanzado:",
        chat_id=chat_id, message_id=call.message.message_id,
        reply_markup=obtener_teclado_niveles("actitud"), parse_mode="Markdown"
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('actitud_'))
def recibir_actitudinal(call):
    chat_id = call.message.chat.id
    nivel_idx = NIVELES_CLAVES.index(call.data.split('_', 1)[1])
    nivel_nombre = NIVELES_NOMBRES[nivel_idx]

    puntos = obtener_puntos(sesiones[chat_id]["actividad"].nombre, "act", nivel_idx)

    sesiones[chat_id]["criterios"]["Actitudinal"] = {"nivel": nivel_nombre, "puntos": puntos}
    sesiones[chat_id]["total_puntos"] += puntos
    sesiones[chat_id]["paso"] = "comunicativo"

    bot.edit_message_text(
        "🗣️ *Criterio Comunicativo*\nSelecciona el nivel alcanzado:",
        chat_id=chat_id, message_id=call.message.message_id,
        reply_markup=obtener_teclado_niveles("com"), parse_mode="Markdown"
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('com_'))
def recibir_comunicativo(call):
    chat_id = call.message.chat.id
    nivel_idx = NIVELES_CLAVES.index(call.data.split('_', 1)[1])
    nivel_nombre = NIVELES_NOMBRES[nivel_idx]

    puntos = obtener_puntos(sesiones[chat_id]["actividad"].nombre, "com", nivel_idx)

    sesiones[chat_id]["criterios"]["Comunicativo"] = {"nivel": nivel_nombre, "puntos": puntos}
    sesiones[chat_id]["total_puntos"] += puntos

    is_foro = "foro de integración" in sesiones[chat_id]["actividad"].nombre.lower()

    if is_foro:
        sesiones[chat_id]["paso"] = "colaborativo"
        bot.edit_message_text(
            "👥 *Criterio Colaborativo*\nSelecciona el nivel alcanzado:",
            chat_id=chat_id, message_id=call.message.message_id,
            reply_markup=obtener_teclado_niveles("col"), parse_mode="Markdown"
        )
    else:
        sesiones[chat_id]["paso"] = "pensamiento"
        bot.edit_message_text(
            "💡 *Pensamiento Crítico*\nSelecciona el nivel alcanzado:",
            chat_id=chat_id, message_id=call.message.message_id,
            reply_markup=obtener_teclado_niveles("pen"), parse_mode="Markdown"
        )


@bot.callback_query_handler(func=lambda call: call.data.startswith('col_'))
def recibir_colaborativo(call):
    chat_id = call.message.chat.id
    nivel_idx = NIVELES_CLAVES.index(call.data.split('_', 1)[1])
    nivel_nombre = NIVELES_NOMBRES[nivel_idx]

    puntos = obtener_puntos(sesiones[chat_id]["actividad"].nombre, "col", nivel_idx)

    sesiones[chat_id]["criterios"]["Colaborativo"] = {"nivel": nivel_nombre, "puntos": puntos}
    sesiones[chat_id]["total_puntos"] += puntos
    sesiones[chat_id]["paso"] = "pensamiento"

    bot.edit_message_text(
        "💡 *Pensamiento Crítico*\nSelecciona el nivel alcanzado:",
        chat_id=chat_id, message_id=call.message.message_id,
        reply_markup=obtener_teclado_niveles("pen"), parse_mode="Markdown"
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('pen_'))
def recibir_pensamiento(call):
    chat_id = call.message.chat.id
    nivel_idx = NIVELES_CLAVES.index(call.data.split('_', 1)[1])
    nivel_nombre = NIVELES_NOMBRES[nivel_idx]

    puntos = obtener_puntos(sesiones[chat_id]["actividad"].nombre, "pen", nivel_idx)

    sesiones[chat_id]["criterios"]["Pensamiento crítico"] = {"nivel": nivel_nombre, "puntos": puntos}
    sesiones[chat_id]["total_puntos"] += puntos

    bot.edit_message_text(
        "✅ Rúbrica completa.\n\n¿Deseas agregar observaciones adicionales para el estudiante?",
        chat_id=chat_id, message_id=call.message.message_id,
        reply_markup=obtener_teclado_obs()
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('obs_'))
def recibir_opcion_observaciones(call):
    chat_id = call.message.chat.id
    opcion = call.data.split('_')[1]

    if opcion == "ninguna":
        sesiones[chat_id]["observaciones"] = ""
        sesiones[chat_id]["es_error_formato"] = False
        evaluar_o_encolar(chat_id, call.message.message_id)
    elif opcion == "formato":
        sesiones[chat_id]["paso"] = "escribir_obs_formato"
        bot.edit_message_text(
            "⚠️ *Error de formato*\nEscribe el detalle (Ej: Entregó .docx en vez de .pptx):",
            chat_id=chat_id, message_id=call.message.message_id, parse_mode="Markdown"
        )
    else:
        sesiones[chat_id]["paso"] = "escribir_obs"
        bot.edit_message_text(
            "📝 Escribe tus observaciones para el estudiante:",
            chat_id=chat_id, message_id=call.message.message_id
        )


@bot.message_handler(func=lambda message: sesiones.get(message.chat.id, {}).get("paso") in ["escribir_obs", "escribir_obs_formato"])
def recibir_texto_observaciones(message):
    chat_id = message.chat.id
    if message.text.startswith('/'): return

    paso_actual = sesiones[chat_id]["paso"]
    texto = message.text

    if paso_actual == "escribir_obs_formato":
        sesiones[chat_id]["observaciones"] = texto
        sesiones[chat_id]["es_error_formato"] = True
    else:
        sesiones[chat_id]["observaciones"] = texto
        sesiones[chat_id]["es_error_formato"] = False

    msg_espera = bot.send_message(chat_id, "⏳ Procesando...")
    evaluar_o_encolar(chat_id, msg_espera.message_id)


def evaluar_o_encolar(chat_id, message_id_to_edit):
    datos = sesiones[chat_id]
    if datos.get("modo") == "batch":
        datos["cola"].append({
            "estudiante": datos["estudiante"],
            "criterios": datos["criterios"].copy(),
            "total_puntos": datos["total_puntos"],
            "observaciones": datos.get("observaciones", ""),
            "es_error_formato": datos.get("es_error_formato", False)
        })
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("➕ Evaluar a otro", callback_data="batch_add"),
            InlineKeyboardButton("🚀 Generar lote", callback_data="batch_run")
        )

        bot.edit_message_text(
            f"✅ *{datos['estudiante']}* guardado en la cola.\n"
            f"Estudiantes en espera: {len(datos['cola'])}\n\n"
            f"¿Qué deseas hacer?",
            chat_id=chat_id, message_id=message_id_to_edit, reply_markup=markup, parse_mode="Markdown"
        )
    else:
        procesar_generacion_individual(
            chat_id, message_id_to_edit,
            datos["estudiante"], datos["criterios"], datos["total_puntos"], datos.get("observaciones", ""), datos.get("es_error_formato", False)
        )


@bot.callback_query_handler(func=lambda call: call.data == 'batch_add')
def batch_add(call):
    chat_id = call.message.chat.id
    sesiones[chat_id]["criterios"] = {}
    sesiones[chat_id]["total_puntos"] = 0.0
    sesiones[chat_id]["paso"] = "nombre"
    bot.edit_message_text("✍️ Escribe el nombre del siguiente estudiante:", chat_id=chat_id, message_id=call.message.message_id)


@bot.callback_query_handler(func=lambda call: call.data == 'batch_run')
def batch_run(call):
    chat_id = call.message.chat.id
    cola = sesiones[chat_id].get("cola", [])
    bot_log("INFO", f"Iniciando procesamiento de lote para {len(cola)} estudiantes.")
    bot.edit_message_text(f"🚀 Generando lote de {len(cola)} retroalimentaciones. Esto tomará un momento...", chat_id=chat_id, message_id=call.message.message_id)

    for idx, item in enumerate(cola):
        bot.send_message(chat_id, f"⏳ Evaluando a {item['estudiante']} ({idx+1}/{len(cola)})...")
        procesar_generacion_individual(chat_id, None, item["estudiante"], item["criterios"], item["total_puntos"], item["observaciones"], item.get("es_error_formato", False))

    del sesiones[chat_id]
    bot_log("INFO", "Lote completado exitosamente.")
    bot.send_message(chat_id, "✨ ¡Lote completado exitosamente! Escribe /evaluar o /lote para iniciar de nuevo.")


def procesar_generacion_individual(chat_id, message_id_to_edit, estudiante, criterios, total_puntos, obs, es_error_formato=False):
    datos = sesiones.get(chat_id)
    if not datos: return
    actividad = datos["actividad"]
    
    modelos_db = db.get_modelos()
    if not modelos_db:
        if message_id_to_edit:
            try: bot.edit_message_text("❌ Error: No hay modelos de IA configurados en el panel del sistema.", chat_id, message_id_to_edit)
            except: pass
        else:
            bot.send_message(chat_id, "❌ Error: No hay modelos de IA configurados en el panel del sistema.")
        return

    modelos_reales = [{"id": m["api_id"], "nombre": m["nombre"], "categoria": m["categoria"]} for m in modelos_db]
    modelo_id_base = datos.get("modelo_id", "auto")

    # Si es error de formato, eliminamos a Haiku de la lista de candidatos
    if es_error_formato:
        modelos_reales = [m for m in modelos_reales if "haiku" not in m["id"].lower()]
        if not modelos_reales:
            modelos_reales = [{"id": "cohere/north-mini-code:free", "nombre": "Cohere (Respaldo)", "categoria": "Gratis"}]

    # 1. Definir el orden de los modelos a intentar con ALEATORIEDAD PURA
    modelos_a_intentar = []
    
    if modelo_id_base == "auto" or (es_error_formato and "haiku" in modelo_id_base.lower()):
        # Tira los dados para cualquier modelo de la lista en cada evaluación individual o de lote
        siguiente_idx = random.randint(0, len(modelos_reales) - 1)
        modelo_principal = modelos_reales[siguiente_idx]
        bot_log("INFO", f"[{estudiante}] Modelo aleatorio seleccionado: {modelo_principal['nombre']}.")
    else:
        modelo_principal = next((m for m in modelos_reales if m["id"] == modelo_id_base), modelos_reales[0])

    modelos_a_intentar.append(modelo_principal)

    # 1.5 Paracaídas inteligente: Dar preferencia a modelos Gratis si el principal falla
    modelos_fallback = [m for m in modelos_reales if m["id"] != modelo_principal["id"]]
    random.shuffle(modelos_fallback) 
    modelos_fallback.sort(key=lambda x: 0 if x["categoria"].lower() == "gratis" else 1) 
    
    modelos_a_intentar.extend(modelos_fallback)

    try:
        builder = PromptBuilder(
            directrices=db.get_all_directrices(),
            actividad=actividad,
            estudiante=estudiante,
            calificacion=total_puntos,
            criterios_evaluados=criterios,
            observaciones=obs,
            es_error_formato=es_error_formato
        )
        prompt = builder.build()
        api_key = os.getenv("OPENROUTER_API_KEY")

        texto_generado = None
        modelo_exitoso = None
        ultimo_error = None

        bot_log("INFO", f"[{estudiante}] Iniciando peticiones a OpenRouter.")

        # 2. Bucle de intentos (El Salvavidas)
        for intento, modelo_actual in enumerate(modelos_a_intentar):
            if message_id_to_edit:
                if intento == 0:
                    mensaje = f"⏳ Redactando con {modelo_actual['nombre']}..."
                else:
                    mensaje = f"🔄 Servidor saturado. Reintentando con {modelo_actual['nombre']}..."
                
                try: bot.edit_message_text(mensaje, chat_id=chat_id, message_id=message_id_to_edit)
                except Exception: pass
            
            bot_log("INFO", f"[{estudiante}] Intentando API con modelo: {modelo_actual['nombre']}")
            start_time = time.time()
            try:
                texto_generado = ia_client.generar(prompt, api_key, modelo_actual["id"], 0.65, 4000)
                elapsed = time.time() - start_time
                bot_log("INFO", f"[{estudiante}] ÉXITO con {modelo_actual['nombre']}. Tiempo: {elapsed:.2f}s.")
                
                if texto_generado.endswith((" y", " con", " el", " la", " los", " las", " de", " un", " una", " proced", " funcion")):
                    bot_log("WARNING", f"[{estudiante}] ATENCIÓN: El texto parece haberse truncado.")

                modelo_exitoso = modelo_actual
                break
            except Exception as e:
                elapsed = time.time() - start_time
                ultimo_error = e
                bot_log("ERROR", f"[{estudiante}] FALLÓ {modelo_actual['nombre']} tras {elapsed:.2f}s. Error: {e}")
                time.sleep(2)
                continue

        if not texto_generado:
            bot_log("ERROR", f"[{estudiante}] TODOS los modelos fallaron. Último error: {ultimo_error}")
            if message_id_to_edit:
                try: bot.edit_message_text(f"❌ Ocurrió un error crítico con {estudiante} y todos los modelos fallaron. Último error: {ultimo_error}", chat_id, message_id_to_edit)
                except: bot.send_message(chat_id, f"❌ Ocurrió un error crítico con {estudiante} y todos los modelos fallaron.")
            else:
                bot.send_message(chat_id, f"❌ Ocurrió un error con {estudiante}: {ultimo_error}")
            return

        # 3. Guardar y enviar archivos
        item = Retroalimentacion(
            estudiante, actividad.nombre, texto_generado,
            modelo_exitoso["nombre"], total_puntos, criterios, obs, prompt, 0.65
        )
        db.create_history(item, actividad.id)

        dirs = db.get_all_directrices()
        n_ase = dirs.get("asesor_nombre", "")
        id_ase = dirs.get("asesor_id", "")

        word_bytes = docx_bytes("", texto_generado, n_ase, id_ase)
        html_text = feedback_to_moodle_html(texto_generado, n_ase, id_ase)
        nombre_base = generar_nombre_archivo(estudiante, actividad.nombre)

        if message_id_to_edit:
            try: bot.delete_message(chat_id, message_id_to_edit)
            except Exception: pass
            message_id_to_edit = None

        word_buffer = io.BytesIO(word_bytes)
        word_buffer.name = f"{nombre_base}.docx"
        html_buffer = io.BytesIO(html_text.encode('utf-8'))
        html_buffer.name = f"{nombre_base}.html"

        bot.send_document(chat_id, document=word_buffer, caption=f"📄 Word: {estudiante} ({modelo_exitoso['nombre']})")
        bot.send_document(chat_id, document=html_buffer, caption=f"🌐 HTML: {estudiante}")

        if "foro de integración" in actividad.nombre.lower():
            bot.send_message(chat_id, f"🔢 *Calificación de {estudiante}:* `{total_puntos:.1f} / 100`", parse_mode="Markdown")

        if datos.get("modo") == "individual":
            bot.send_message(chat_id, "✨ ¡Listo! Escribe /evaluar o /lote para generar otra.")
            del sesiones[chat_id]

    except Exception as e:
        bot_log("ERROR", f"[{estudiante}] Error inesperado al procesar: {e}")
        if message_id_to_edit:
            try: bot.edit_message_text(f"❌ Ocurrió un error procesando a {estudiante}: {e}", chat_id, message_id_to_edit)
            except Exception: bot.send_message(chat_id, f"❌ Ocurrió un error procesando a {estudiante}: {e}")
        else:
            bot.send_message(chat_id, f"❌ Ocurrió un error procesando a {estudiante}: {e}")


if __name__ == '__main__':
    # 3. MODO POLLING PARA HEROKU WORKER DYNO
    bot.remove_webhook()
    time.sleep(1)

    comandos = [
        BotCommand("evaluar", "👤 Iniciar evaluación individual"),
        BotCommand("lote", "📦 Iniciar evaluación masiva en lote"),
        BotCommand("cancelar", "🚫 Cancelar la sesión actual"),
        BotCommand("ayuda", "❓ Ver instrucciones del bot")
    ]
    bot.set_my_commands(comandos)
    
    bot_log("INFO", "Bot de Telegram iniciado en modo Polling (Worker de Heroku)...")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
