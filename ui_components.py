"""Componentes reutilizables de la interfaz de usuario con edición habilitada."""

from __future__ import annotations

from typing import Any
import streamlit as st
from datetime import datetime, timedelta

from models import Actividad, Criterio, Nivel, Recurso, Rubrica, Frase
from utils import docx_bytes, pdf_bytes, sanitize_filename, get_activity_code, feedback_to_moodle_html, generar_nombre_archivo


def header() -> None:
    st.title("Generador Inteligente de Retroalimentaciones Formativas con IA")
    st.caption("Diseñado para evaluación transparente, personalizada y asistida por IA para Asesores Virtuales.")
    st.markdown("---")


def info_card(title: str, text: str) -> None:
    st.info(f"**{title}**\n\n{text}")


def rubric_manual_form() -> tuple[Rubrica, bool]:
    st.markdown("#### 📐 Matriz de Desempeño de la Rúbrica")
    
    # Interruptor dinámico para mostrar u ocultar la pestaña Colaborativo
    es_foro = st.checkbox("Habilitar 5to criterio (Colaborativo) para Foro de Integración")
    
    with st.form("form_rubrica_manual_matriz"):
        nombre = st.text_input("Nombre de la rúbrica", placeholder="Ej. Rúbrica Actividad 4")
        
        criterios_nombres = ["Cognitivo", "Actitudinal", "Comunicativo", "Pensamiento crítico"]
        if es_foro:
            criterios_nombres.insert(3, "Colaborativo")
            
        niveles_nombres = ["Experto", "Capacitado", "Aceptable", "Aprendiz", "Requiere apoyo", "No evaluable"]

        criterios_objetos: list[Criterio] = []
        resumen_texto_lineas: list[str] = [f"RÚBRICA: {nombre}\n"]
        tabs = st.tabs(criterios_nombres)

        for idx, crit_nombre in enumerate(criterios_nombres):
            with tabs[idx]:
                niveles_objetos: list[Nivel] = []
                resumen_texto_lineas.append(f"\n--- CRITERIO: {crit_nombre.upper()} ---")
                for niv_nombre in niveles_nombres:
                    desc = st.text_area(f"Nivel: {niv_nombre}", key=f"input_rub_{crit_nombre}_{niv_nombre}", height=70)
                    niveles_objetos.append(Nivel(nombre=niv_nombre, descripcion=desc))
                    resumen_texto_lineas.append(f"[{niv_nombre}]: {desc}")
                criterios_objetos.append(Criterio(nombre=crit_nombre, niveles=niveles_objetos))

        contenido_completo = "\n".join(resumen_texto_lineas)
        submitted = st.form_submit_button("💾 Guardar Rúbrica", type="primary")

    return Rubrica(nombre=nombre, contenido=contenido_completo, criterios=criterios_objetos), submitted


def rubric_import_form() -> tuple[Rubrica, bool]:
    with st.form("form_rubrica_import"):
        nombre = st.text_input("Nombre de la rúbrica a importar")
        contenido = st.text_area("Pega aquí el texto completo", height=220)
        submitted = st.form_submit_button("Importar y guardar")
    return Rubrica(nombre=nombre, contenido=contenido), submitted


def recurso_global_form() -> tuple[Recurso, bool]:
    with st.form("form_recurso_global"):
        titulo = st.text_input("Nombre / Título del recurso")
        tipo = st.selectbox("Tipo de recurso", ["Video", "Artículo", "Enlace", "PDF", "Otro"])
        url = st.text_input("URL del recurso")
        descripcion = st.text_area("Descripción / Propósito", height=60)
        submitted = st.form_submit_button("Guardar en Catálogo")
    return Recurso(titulo=titulo, tipo=tipo, url=url, descripcion=descripcion), submitted


def frase_global_form() -> tuple[Frase, bool]:
    with st.form("form_frase_global"):
        texto = st.text_area("Frase célebre (sin comillas)", height=60)
        autor = st.text_input("Autor")
        submitted = st.form_submit_button("Guardar Frase")
    return Frase(texto=texto, autor=autor), submitted


def activity_form(rubricas: list[Any], frases: list[Frase], recursos: list[Recurso]) -> tuple[Actividad, int | None, int | None, list[int], bool]:
    rubric_opts = {"Sin rúbrica": None} | {r["nombre"]: r["id"] for r in rubricas}
    frase_opts = {"Sin frase": None} | {f'"{f.texto[:40]}..." - {f.autor}': f.id for f in frases}
    recurso_opts = {r.titulo: r.id for r in recursos}

    with st.form("form_actividad"):
        nombre = st.text_input("Nombre de la actividad")
        proposito = st.text_area("Propósito de la actividad", height=60)
        instrucciones = st.text_area("Instrucciones detalladas", height=90)
        
        col1, col2 = st.columns(2)
        selected_rubric = col1.selectbox("Rúbrica asociada", list(rubric_opts.keys()))
        selected_frase = col2.selectbox("Frase de cierre asociada", list(frase_opts.keys()))
        
        selected_recursos_nombres = st.multiselect("Recursos asociados a esta actividad", list(recurso_opts.keys()))
        selected_recursos_ids = [recurso_opts[n] for n in selected_recursos_nombres if n in recurso_opts]

        submitted = st.form_submit_button("Guardar Actividad Integrada", type="primary")

    return Actividad(nombre=nombre, proposito=proposito, instrucciones=instrucciones), rubric_opts[selected_rubric], frase_opts[selected_frase], selected_recursos_ids, submitted


def evaluation_inputs(act_nombre: str = "") -> tuple[dict[str, dict[str, Any]], float]:
    st.markdown("#### 🎯 Evaluador por Criterio de Desempeño")
    
    is_foro = "foro de integración" in act_nombre.lower()
    
    if is_foro:
        escala_cog = {"Experto (40 pts)": ("Experto", 40.0), "Capacitado (34 pts)": ("Capacitado", 34.0), "Aceptable (32 pts)": ("Aceptable", 32.0), "Aprendiz (28 pts)": ("Aprendiz", 28.0), "Requiere apoyo (24 pts)": ("Requiere apoyo", 24.0), "No evaluable (0 pts)": ("No evaluable", 0.0)}
        escala_rest = {"Experto (15 pts)": ("Experto", 15.0), "Capacitado (14 pts)": ("Capacitado", 14.0), "Aceptable (12 pts)": ("Aceptable", 12.0), "Aprendiz (11 pts)": ("Aprendiz", 11.0), "Requiere apoyo (9 pts)": ("Requiere apoyo", 9.0), "No evaluable (0 pts)": ("No evaluable", 0.0)}
    else:
        escala_cog = {"Experto (40 pts)": ("Experto", 40.0), "Capacitado (36 pts)": ("Capacitado", 36.0), "Aceptable (32 pts)": ("Aceptable", 32.0), "Aprendiz (28 pts)": ("Aprendiz", 28.0), "Requiere apoyo (24 pts)": ("Requiere apoyo", 24.0), "No evaluable (0 pts)": ("No evaluable", 0.0)}
        escala_rest = {"Experto (20 pts)": ("Experto", 20.0), "Capacitado (18 pts)": ("Capacitado", 18.0), "Aceptable (16 pts)": ("Aceptable", 16.0), "Aprendiz (14 pts)": ("Aprendiz", 14.0), "Requiere apoyo (12 pts)": ("Requiere apoyo", 12.0), "No evaluable (0 pts)": ("No evaluable", 0.0)}

    criterios = {}
    total = 0.0

    c1, c2 = st.columns(2)
    with c1:
        s_cog = st.selectbox("1. Cognitivo", list(escala_cog.keys()), index=0); n_cog, p_cog = escala_cog[s_cog]; criterios["Cognitivo"] = {"nivel": n_cog, "puntos": p_cog}; total += p_cog
        s_act = st.selectbox("2. Actitudinal", list(escala_rest.keys()), index=0); n_act, p_act = escala_rest[s_act]; criterios["Actitudinal"] = {"nivel": n_act, "puntos": p_act}; total += p_act
        if is_foro:
            s_col = st.selectbox("4. Colaborativo", list(escala_rest.keys()), index=0); n_col, p_col = escala_rest[s_col]; criterios["Colaborativo"] = {"nivel": n_col, "puntos": p_col}; total += p_col
    with c2:
        s_com = st.selectbox("3. Comunicativo", list(escala_rest.keys()), index=0); n_com, p_com = escala_rest[s_com]; criterios["Comunicativo"] = {"nivel": n_com, "puntos": p_com}; total += p_com
        s_pen = st.selectbox("5. Pensamiento crítico" if is_foro else "4. Pensamiento crítico", list(escala_rest.keys()), index=0); n_pen, p_pen = escala_rest[s_pen]; criterios["Pensamiento crítico"] = {"nivel": n_pen, "puntos": p_pen}; total += p_pen

    st.info(f"💡 **Calificación Total:** `{total:.1f} / 100 pts`")
    return criterios, total


def download_buttons(filename_prefix: str, text: str, html_text: str, docx_data: bytes, pdf_data: bytes, json_data: str) -> None:
    st.markdown("---")
    st.markdown("### 📥 Descargar Retroalimentación")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.download_button("📄 Word (.docx)", docx_data, f"{filename_prefix}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", width="stretch")
    c2.download_button("📕 PDF (.pdf)", pdf_data, f"{filename_prefix}.pdf", "application/pdf", width="stretch")
    c3.download_button("📝 Texto (.txt)", text.encode("utf-8"), f"{filename_prefix}.txt", "text/plain", width="stretch")
    c4.download_button("💾 Datos (.json)", json_data.encode("utf-8"), f"{filename_prefix}.json", "application/json", width="stretch")
    c5.download_button("🌐 HTML (.html)", html_text.encode("utf-8"), f"{filename_prefix}.html", "text/html", width="stretch")


def history_card(row: Any, act_map: dict = None) -> None:
    # 1. Obtener fecha de forma segura
    fecha_str = row.get("fecha", "Sin fecha")
    if fecha_str and fecha_str != "Sin fecha":
        try:
            dt_utc = datetime.strptime(fecha_str, "%Y-%m-%d %H:%M:%S")
            dt_utc_minus_6 = dt_utc - timedelta(hours=6)
            fecha = dt_utc_minus_6.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            fecha = fecha_str
    else:
        fecha = "Sin fecha"

    estudiante = row.get("estudiante", "Estudiante")
    
    # 2. EL TRUCO MAESTRO: Buscar el nombre cruzando el ID numérico
    if act_map and row.get("actividad_id") in act_map:
        actividad = act_map[row["actividad_id"]]
    else:
        # Respaldo extremo por si el ID no existe
        actividad = row.get("actividad_nombre") or row.get("actividad") or "General"
        
    calificacion = row.get("calificacion", 0.0)
    row_id = row.get("id", 0)

    with st.expander(f"👤 {estudiante} — {actividad} ({calificacion:.1f} pts) — 📅 {fecha}"):
        st.markdown(row.get("retroalimentacion", ""))
        
        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        
        # 3. Nombramiento infalible
        nombre_base = generar_nombre_archivo(estudiante, actividad)
        
        docx_data = docx_bytes("", row.get("retroalimentacion", ""))
        pdf_data = pdf_bytes("", row.get("retroalimentacion", ""))
        html_text = feedback_to_moodle_html(row.get("retroalimentacion", ""))
        
        c1.download_button("📄 Word (.docx)", docx_data, f"{nombre_base}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", key=f"dl_word_{row_id}", width="stretch")
        c2.download_button("📕 PDF (.pdf)", pdf_data, f"{nombre_base}.pdf", "application/pdf", key=f"dl_pdf_{row_id}", width="stretch")
        c3.download_button("🌐 HTML (.html)", html_text.encode("utf-8"), f"{nombre_base}.html", "text/html", key=f"dl_html_{row_id}", width="stretch")
