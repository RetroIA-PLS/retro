"""Interfaz Streamlit con módulos de edición integrados."""

from __future__ import annotations

import json
import os
import pandas as pd
from datetime import datetime, date
from typing import Any

import streamlit as st
from dotenv import load_dotenv

from config import (
    APP_ICON, APP_LAYOUT, APP_TITLE, DEFAULT_MAX_TOKENS, DEFAULT_MODEL_ID,
    DEFAULT_MODEL_NAME, DEFAULT_TEMPERATURE, MODELOS_GRATIS, MODELOS_OPENROUTER, MODELOS_PAGO
)
from database import DatabaseManager
from ia_client import IAClient
from models import Actividad, Recurso, Retroalimentacion, Rubrica
from prompt_builder import PromptBuilder
from styles import app_css
from ui_components import (
    activity_form, download_buttons, evaluation_inputs, frase_global_form,
    header, history_card, recurso_global_form, rubric_import_form, rubric_manual_form
)
from utils import docx_bytes, export_json, feedback_to_moodle_html, pdf_bytes, sanitize_filename, get_activity_code, create_zip, generar_nombre_archivo


# Clases "Dummy" para aislar la UI de los errores de los modelos originales
class _Dummy: pass

class RetroalimentacionApp:
    def __init__(self, db: DatabaseManager) -> None:
        self.db = db
        self.ia_client = IAClient("openrouter")

    def run(self) -> None:
        load_dotenv()
        st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout=APP_LAYOUT)
        st.markdown(app_css(), unsafe_allow_html=True)
        self._state()

        # Extraer el nombre del asesor para la interfaz
        dirs_cache = self.db.get_all_directrices()
        nombre_asesor = dirs_cache.get("asesor_nombre", "Asesor").split()[0] if dirs_cache.get("asesor_nombre") else "Asesor"

        # --- MENÚ VERTICAL EN SIDEBAR ---
        with st.sidebar:
            st.markdown(f"### {nombre_asesor}")
            if st.button("Cerrar sesión", width="stretch"):
                st.info("Sesión cerrada (Simulación)")
            
            st.markdown("---")
            st.info("Sin documento activo", icon="📄")
            st.markdown("---")
            st.caption("Flujo de trabajo")
            
            opciones_navegacion = [
                "🏠 1. Generar retroalimentación",
                "📜 2. Historial y Lotes",
                "📋 3. Configuración de actividades",
                "🤖 4. Configuración IA y Perfil",
                "⚙️ 5. Configuración del Sistema",
                "💬 6. Generador de Foros"
            ]
            
            pagina_actual = st.radio(
                label="Navegación",
                options=opciones_navegacion,
                label_visibility="collapsed"
            )

        # --- CONTENIDO PRINCIPAL ---
        header()
        
        if pagina_actual == opciones_navegacion[0]:
            self.tab_generate()
        elif pagina_actual == opciones_navegacion[1]:
            self.tab_history()
        elif pagina_actual == opciones_navegacion[2]:
            self.tab_activities()
        elif pagina_actual == opciones_navegacion[3]:
            self.tab_ai_config()
        elif pagina_actual == opciones_navegacion[4]:
            self.tab_settings()
        elif pagina_actual == opciones_navegacion[5]:
            self.tab_forums()

        st.markdown("<br><hr><center><small class='small-muted'>Retroalimentaciones Formativas IA</small></center>", unsafe_allow_html=True)

    def _state(self) -> None:
        defaults = {
            "api_key": os.getenv("OPENROUTER_API_KEY", ""),
            "model_name": DEFAULT_MODEL_NAME,
            "model_id": DEFAULT_MODEL_ID,
            "temperature": DEFAULT_TEMPERATURE,
            "max_tokens": DEFAULT_MAX_TOKENS,
            "last_feedback": "",
            "last_prompt": "",
            "batch_queue": []
        }
        for key, value in defaults.items():
            st.session_state.setdefault(key, value)

    def tab_generate(self) -> None:
        activities = self.db.list_activities()
        if not activities:
            st.warning("Primero registra una actividad en la Configuración de Actividades.")
            return
            
        labels = {f"{r['nombre']}": r["id"] for r in activities}
        
        modo = st.radio("Modo de Evaluación", ["👤 Individual", "📦 Lote (Batch)"], horizontal=True)
        st.markdown("---")
        
        selected = st.selectbox("Selecciona la Actividad a evaluar", list(labels.keys()))
        activity = self.db.get_activity(labels[selected])
        if not activity: return

        # --- SELECCIÓN DEL MODELO EN LA PANTALLA PRINCIPAL ---
        modelos = self.db.get_modelos()
        if not modelos:
            st.error("No hay modelos de IA configurados. Ve a 'Configuración del Sistema' para agregar uno.")
            return

        with st.expander("🤖 Configuración del Modelo de IA (Despliega para cambiar)", expanded=False):
            col_m1, col_m2, col_m3 = st.columns([2, 1, 1])
            
            opciones_modelos = {f"{m['nombre']} ({m['categoria']})": m for m in modelos}
            nombres_modelos = list(opciones_modelos.keys())
            
            idx_modelo = 0
            for i, nom in enumerate(nombres_modelos):
                if opciones_modelos[nom]['api_id'] == st.session_state.model_id:
                    idx_modelo = i
                    break

            sel_nombre = col_m1.selectbox("Modelo", nombres_modelos, index=idx_modelo)
            mod_seleccionado = opciones_modelos[sel_nombre]
            
            st.session_state.model_name = mod_seleccionado["nombre"]
            st.session_state.model_id = mod_seleccionado["api_id"]
            
            st.session_state.temperature = col_m2.slider("Temperatura", 0.0, 1.5, float(st.session_state.temperature), 0.1)
            st.session_state.max_tokens = col_m3.slider("Tokens (Max)", 200, 8000, int(st.session_state.max_tokens), 100)

        # =========================================================
        # LA BURBUJA: Todo esto pasa sin recargar la pantalla
        # =========================================================
        with st.form("evaluacion_form"):
            st.markdown("### 📝 Datos de la Evaluación")
            estudiante = st.text_input("Nombre del Estudiante", placeholder="Ej. Argelia")

            criterios_evaluados, calificacion_total = evaluation_inputs(activity.nombre)
            
            tipo_obs = st.radio("¿Deseas agregar observaciones manuales?", ["❌ No, generar directo", "📝 Sí, escribir nota al estudiante"], horizontal=True)
            formato_incorrecto = st.checkbox("⚠️ Evaluar por formato incorrecto (Genera retroalimentación breve y unificada)", help="Activa esto si entregó en un formato equivocado (ej. DOCX en vez de PPTX). La IA hará un texto corto sin desglosar criterios.")
            
            # Dentro de un form, los campos de texto siempre deben estar visibles, 
            # pero solo los usamos si el asesor lo indicó en las opciones.
            observaciones_usuario = st.text_area("Escribe tus observaciones (O especifica el error de formato si aplica):", height=100)

            st.markdown("---")
            if modo == "👤 Individual":
                # Este botón es el único que rompe la burbuja y envía los datos
                submit_eval = st.form_submit_button("✨ Generar Retroalimentación", type="primary", use_container_width=True)
            else:
                submit_eval = st.form_submit_button("➕ Agregar a la cola de procesamiento", type="primary", use_container_width=True)

        # =========================================================
        # PROCESAMIENTO (Solo ocurre cuando se presiona el botón)
        # =========================================================
        if submit_eval:
            if formato_incorrecto:
                texto_base = observaciones_usuario if observaciones_usuario else "La actividad se entregó en un formato incorrecto (ej. procesador de textos en lugar de presentación con diapositivas)."
                observaciones_finales = f"¡INSTRUCCIÓN CRÍTICA DE SISTEMA!: Esta actividad se evalúa con la calificación mínima aprobatoria EXCLUSIVAMENTE porque no cumple con el formato de entrega solicitado. IGNORA por completo el desarrollo detallado e individual de cada criterio de la rúbrica (Cognitivo, Actitudinal, etc.). En su lugar, redacta una retroalimentación BREVE y unificada (1 o 2 párrafos a lo mucho). El mensaje central a desarrollar es exactamente este: '{texto_base}'. Usa un tono empático pero firme invitando a leer las instrucciones. NO desgloses los criterios con subtítulos."
            else:
                observaciones_finales = observaciones_usuario

            builder = PromptBuilder(
                directrices=self.db.get_all_directrices(),
                actividad=activity,
                estudiante=estudiante,
                calificacion=calificacion_total,
                criterios_evaluados=criterios_evaluados,
                observaciones=observaciones_finales,
            )

            # Ocultamos la vista previa del prompt para no ensuciar la interfaz, 
            # pero la procesamos internamente.
            if modo == "👤 Individual":
                self._generate_feedback(builder, activity.id)
            else:
                validation = builder.validate()
                if validation.ok:
                    st.session_state.batch_queue.append({
                        "estudiante": estudiante,
                        "calificacion_total": calificacion_total,
                        "criterios_evaluados": criterios_evaluados,
                        "observaciones": observaciones_finales
                    })
                    st.success(f"✅ {estudiante} agregado a la cola de procesamiento.")
                else:
                    for error in validation.errors: st.error(error)

        # =========================================================
        # MOSTRAR RESULTADOS (Fuera del form para no perder las descargas)
        # =========================================================
        if modo == "👤 Individual":
            if st.session_state.last_feedback:
                dirs = self.db.get_all_directrices()
                n_ase = dirs.get("asesor_nombre", "")
                id_ase = dirs.get("asesor_id", "")
                
                title = generar_nombre_archivo(estudiante, activity.nombre)
                html_feedback = feedback_to_moodle_html(st.session_state.last_feedback, n_ase, id_ase)
                
                st.subheader("Resultado")
                if "foro de integración" in activity.nombre.lower():
                    st.info(f"🔢 **Calificación para Moodle:** `{calificacion_total:.1f} / 100`")
                    
                st.markdown(st.session_state.last_feedback)
                with st.expander("📋 HTML compacto para Moodle"):
                    st.text_area("Código HTML", value=html_feedback, height=220, key="html_feedback_moodle")
                
                payload = json.dumps({"retroalimentacion": st.session_state.last_feedback, "prompt": st.session_state.last_prompt}, ensure_ascii=False, indent=2)
                download_buttons(title, st.session_state.last_feedback, html_feedback, docx_bytes("", st.session_state.last_feedback, n_ase, id_ase), pdf_bytes("", st.session_state.last_feedback), payload)
                
        else:
            if st.session_state.batch_queue:
                st.markdown("### 📋 Cola de Processing")
                for i, item in enumerate(st.session_state.batch_queue):
                    st.write(f"{i+1}. **{item['estudiante']}** ({item['calificacion_total']} pts)")
                
                if st.button("🚀 Procesar todo el lote ahora", type="primary"):
                    progress_bar = st.progress(0)
                    total_q = len(st.session_state.batch_queue)
                    
                    for idx, item in enumerate(st.session_state.batch_queue):
                        b = PromptBuilder(self.db.get_all_directrices(), activity, item["estudiante"], item["calificacion_total"], item["criterios_evaluados"], item["observaciones"])
                        prompt = b.build()
                        try:
                            text = self.ia_client.generar(prompt, st.session_state.api_key, st.session_state.model_id, st.session_state.temperature, st.session_state.max_tokens)
                            retro = Retroalimentacion(b.estudiante, activity.nombre, text, st.session_state.model_name, b.calificacion, b.criterios_evaluados, b.observaciones, prompt, st.session_state.temperature)
                            self.db.create_history(retro, activity.id)
                        except Exception as e:
                            st.error(f"Error con {item['estudiante']}: {e}")
                        progress_bar.progress((idx + 1) / total_q)
                    
                    st.session_state.batch_queue.clear()
                    st.success("✨ ¡Lote generado exitosamente! Ve a la pestaña 'Historial' para descargar todos en un archivo ZIP.")

    def _generate_feedback(self, builder: PromptBuilder, activity_id: int | None) -> None:
        validation = builder.validate()
        for error in validation.errors: st.error(error)
        if not validation.ok: return
        
        try:
            with st.spinner("Generando redacción pedagógica original..."):
                prompt = builder.build()
                text = self.ia_client.generar(prompt, st.session_state.api_key, st.session_state.model_id, st.session_state.temperature, st.session_state.max_tokens)
            st.session_state.last_feedback = text
            st.session_state.last_prompt = prompt
            
            item = Retroalimentacion(builder.estudiante, builder.actividad.nombre if builder.actividad else "", text, st.session_state.model_name, builder.calificacion, builder.criterios_evaluados, builder.observaciones, prompt, st.session_state.temperature)
            self.db.create_history(item, activity_id)
            st.success("Guardado en el historial.")
        except Exception as exc:
            st.error(f"Error: {exc}")

    def tab_history(self) -> None:
        st.subheader("📦 Descarga y Gestión de Evaluaciones por Lote")

        lista_actividades = self.db.list_activities()
        activities = {"Todas": None} | {r["nombre"]: r["id"] for r in lista_actividades}
        
        act_map = {r["id"]: r["nombre"] for r in lista_actividades}

        col1, col2 = st.columns(2)
        query = col1.text_input("🔍 Buscar en historial (Estudiante):")
        selected_act_name = col2.selectbox("Filtrar por actividad", list(activities.keys()))
        
        col3, col4 = st.columns(2)
        fecha_desde = col3.date_input("Fecha desde:", value=date(2026, 8, 1))
        fecha_hasta = col4.date_input("Fecha hasta:", value=date.today())
        
        rows = self.db.list_history(
            estudiante=query,
            actividad_id=activities[selected_act_name],
            limit=500,
            fecha_inicio=fecha_desde.strftime("%Y-%m-%d"),
            fecha_fin=fecha_hasta.strftime("%Y-%m-%d")
        )
        
        if not rows: st.info("No hay registros en esas fechas."); return
        st.caption(f"Registros encontrados: {len(rows)}")
        
        with st.expander("📦 Herramienta de Descarga en Lote (ZIP)", expanded=False):
            st.markdown("Selecciona las retroalimentaciones que deseas incluir en el archivo ZIP.")
            
            if "select_all" not in st.session_state:
                st.session_state.select_all = False
            
            col_btn1, col_btn2 = st.columns(2)
            if col_btn1.button("✅ Seleccionar todos", width="stretch"):
                st.session_state.select_all = True
                st.rerun()
            if col_btn2.button("⬜ Deseleccionar todos", width="stretch"):
                st.session_state.select_all = False
                st.rerun()
            
            df_data = []
            for r in rows:
                fecha_val = r.get("fecha", "")
                estudiante_val = r.get("estudiante", "")
                calificacion_val = r.get("calificacion", 0.0)
                
                df_data.append({
                    "Seleccionar": st.session_state.select_all,
                    "Fecha": fecha_val,
                    "Estudiante": estudiante_val,
                    "Calificación": calificacion_val,
                    "ID": r.get("id", 0)
                })
            df = pd.DataFrame(df_data)
            edited_df = st.data_editor(df, hide_index=True, disabled=["Fecha", "Estudiante", "Calificación", "ID"], width="stretch")
            
            dirs = self.db.get_all_directrices()
            n_ase = dirs.get("asesor_nombre", "")
            id_ase = dirs.get("asesor_id", "")
            grupo_actual = dirs.get("grupo", "M00C0G00-000")
            grupo_zip = st.text_input("Grupo (para nombrar el archivo ZIP)", value=grupo_actual)
            
            selected_ids = edited_df[edited_df["Seleccionar"]]["ID"].tolist()
            selected_rows = [r for r in rows if r.get("id", 0) in selected_ids]
            
            if st.button(f"📥 Descargar {len(selected_rows)} archivos en ZIP", type="primary", disabled=len(selected_rows)==0, width="stretch"):
                archivos = []
                for r in selected_rows:
                    est_val = r.get("estudiante", "")
                    
                    if r.get("actividad_id") in act_map:
                        act_val = act_map[r["actividad_id"]]
                    else:
                        act_val = r.get("actividad_nombre") or r.get("actividad") or "General"
                    
                    nombre_base = generar_nombre_archivo(est_val, act_val)
                    docx_data = docx_bytes("", r.get("retroalimentacion", ""), n_ase, id_ase)
                    html_text = feedback_to_moodle_html(r.get("retroalimentacion", ""), n_ase, id_ase)
                    
                    archivos.append((f"{nombre_base}.docx", docx_data))
                    archivos.append((f"{nombre_base}.html", html_text.encode('utf-8')))
                
                zip_bytes = create_zip(archivos)
                act_str = get_activity_code(selected_act_name) if selected_act_name != "Todas" else "Varias"
                st.download_button("💾 Haz clic aquí para guardar tu archivo ZIP", data=zip_bytes, file_name=f"Retros_{grupo_zip}_{act_str}.zip", mime="application/zip", width="stretch")

        st.markdown("---")
        for row in rows: history_card(row, act_map)

    def tab_activities(self) -> None:
        t1, t2, t3, t4 = st.tabs(["📚 Banco de Recursos", "✍️ Banco de Frases", "📐 Rúbricas", "🔗 Ensamblar Actividad"])
        
        with t1:
            st.subheader("Catálogo Global de Recursos")
            rec, sub_rec = recurso_global_form()
            if sub_rec and getattr(rec, "titulo", ""):
                self.db.create_recurso(rec); st.success("Recurso guardado."); st.rerun()
            
            st.markdown("---")
            st.markdown("#### Recursos Guardados (Editar o Eliminar)")
            for r in self.db.list_recursos_globales():
                r_tit = getattr(r, "titulo", "")
                r_tip = getattr(r, "tipo", "Video")
                r_url = getattr(r, "url", "")
                r_des = getattr(r, "descripcion", "")
                
                with st.expander(f"📌 {r_tit} [{r_tip}]"):
                    with st.form(f"form_edit_rec_{r.id}"):
                        e_tit = st.text_input("Título", r_tit)
                        e_tip = st.selectbox("Tipo", ["Video", "Artículo", "Enlace", "PDF", "Otro"], index=["Video", "Artículo", "Enlace", "PDF", "Otro"].index(r_tip) if r_tip in ["Video", "Artículo", "Enlace", "PDF", "Otro"] else 0)
                        e_url = st.text_input("URL", r_url)
                        e_des = st.text_area("Descripción", r_des, height=60)
                        c1, c2 = st.columns(2)
                        if c1.form_submit_button("Actualizar Recurso"):
                            d = _Dummy()
                            d.tipo, d.titulo, d.url, d.descripcion = e_tip, e_tit, e_url, e_des
                            self.db.update_recurso(r.id, d)
                            st.success("Recurso actualizado."); st.rerun()
                        if c2.form_submit_button("Eliminar Recurso"):
                            self.db.delete_recurso(r.id); st.rerun()
                    
        with t2:
            st.subheader("Catálogo Global de Frases Célebres")
            frase, sub_fra = frase_global_form()
            if sub_fra and getattr(frase, "texto", ""):
                self.db.create_frase(frase.texto, frase.autor); st.success("Frase guardada."); st.rerun()
            
            st.markdown("---")
            st.markdown("#### Frases Guardadas (Editar o Eliminar)")
            for f in self.db.list_frases():
                f_txt = str(getattr(f, "texto", ""))
                f_aut = str(getattr(f, "autor", ""))
                with st.expander(f"💬 {f_aut} - {f_txt[:30]}..."):
                    with st.form(f"form_edit_fra_{f.id}"):
                        e_txt = st.text_area("Frase", f_txt, height=60)
                        e_aut = st.text_input("Autor", f_aut)
                        c1, c2 = st.columns(2)
                        if c1.form_submit_button("Actualizar Frase"):
                            self.db.update_frase(f.id, e_txt, e_aut)
                            st.success("Frase actualizada."); st.rerun()
                        if c2.form_submit_button("Eliminar Frase"):
                            self.db.delete_frase(f.id); st.rerun()

        with t3:
            st.subheader("Rúbricas Institucionales")
            mode = st.radio("Modo", ["Manual", "Importar tabla"], horizontal=True)
            rubrica, sub_rub = rubric_manual_form() if mode == "Manual" else rubric_import_form()
            if sub_rub and getattr(rubrica, "nombre", ""):
                try: self.db.create_rubric(rubrica); st.success("Rúbrica guardada."); st.rerun()
                except Exception as e: st.error(f"Error: {e}")
            
            st.markdown("---")
            st.markdown("#### Rúbricas Guardadas (Editar o Eliminar)")
            for r in self.db.list_rubrics():
                with st.expander(r["nombre"]):
                    rub_obj = self.db.get_rubric(r["id"])
                    if not rub_obj: continue
                    with st.form(f"form_edit_rub_{r['id']}"):
                        e_nom = st.text_input("Nombre de la rúbrica", getattr(rub_obj, "nombre", ""))
                        e_cont = st.text_area("Contenido base", getattr(rub_obj, "contenido", ""), height=150)
                        c1, c2 = st.columns(2)
                        if c1.form_submit_button("Actualizar Rúbrica"):
                            d = _Dummy()
                            d.nombre, d.contenido = e_nom, e_cont
                            self.db.update_rubric(r["id"], d)
                            st.success("Rúbrica actualizada."); st.rerun()
                        if c2.form_submit_button("Eliminar Rúbrica"):
                            self.db.delete_rubric(r["id"]); st.rerun()

        with t4:
            st.subheader("Configurar Nueva Actividad")
            st.caption("Une la rúbrica, la frase y los recursos para crear la actividad final.")
            act, r_id, f_id, rec_ids, sub_act = activity_form(self.db.list_rubrics(), self.db.list_frases(), self.db.list_recursos_globales())
            if sub_act and getattr(act, "nombre", ""):
                try: self.db.create_activity(act, r_id, f_id, rec_ids); st.success("Actividad Ensamblada."); st.rerun()
                except Exception as e: st.error(f"Error: {e}")

            st.markdown("---")
            st.markdown("#### Actividades Configuradas (Editar Ensamblado o Eliminar)")
            all_rubrics = self.db.list_rubrics()
            all_frases = self.db.list_frases()
            all_recursos = self.db.list_recursos_globales()

            for a_raw in self.db.list_activities():
                act_obj = self.db.get_activity(a_raw["id"])
                if not act_obj: continue
                
                a_nom = str(getattr(act_obj, "nombre", ""))
                
                with st.expander(f"⚙️ Editar: {a_nom}"):
                    with st.form(f"form_edit_act_{act_obj.id}"):
                        e_nom = st.text_input("Nombre de la actividad", a_nom)
                        e_pro = st.text_area("Propósito de la actividad", getattr(act_obj, "proposito", ""), height=60)
                        e_ins = st.text_area("Instrucciones detalladas", getattr(act_obj, "instrucciones", ""), height=90)

                        rub_val = getattr(act_obj, "rubrica", None)
                        rub_id = getattr(rub_val, "id", None) if rub_val else None
                        
                        fra_val = getattr(act_obj, "frase", None)
                        fra_id = getattr(fra_val, "id", None) if fra_val else None

                        rubric_opts = {"Sin rúbrica": None} | {r["nombre"]: r["id"] for r in all_rubrics}
                        frase_opts = {"Sin frase": None} | {f'"{str(getattr(f, "texto", ""))[:40]}..." - {str(getattr(f, "autor", ""))}': f.id for f in all_frases}
                        recurso_opts = {getattr(r, "titulo", ""): r.id for r in all_recursos}

                        try:
                            curr_rub_idx = list(rubric_opts.values()).index(rub_id)
                        except ValueError:
                            curr_rub_idx = 0

                        try:
                            curr_fra_idx = list(frase_opts.values()).index(fra_id)
                        except ValueError:
                            curr_fra_idx = 0

                        recs_list = getattr(act_obj, "recursos", [])
                        curr_recs_nombres = [getattr(r, "titulo", "") for r in recs_list if getattr(r, "titulo", "") in recurso_opts]

                        col1, col2 = st.columns(2)
                        e_rub = col1.selectbox("Rúbrica asociada", list(rubric_opts.keys()), index=curr_rub_idx)
                        e_fra = col2.selectbox("Frase de cierre asociada", list(frase_opts.keys()), index=curr_fra_idx)
                        
                        e_recs = st.multiselect("Recursos asociados", list(recurso_opts.keys()), default=curr_recs_nombres)
                        e_recs_ids = [recurso_opts[n] for n in e_recs if n in recurso_opts]

                        c1, c2 = st.columns(2)
                        if c1.form_submit_button("Actualizar Ensamblado"):
                            g_val = getattr(act_obj, "grupo", "M00C0G00-000")
                            o_val = getattr(act_obj, "orden", 0)
                            self.db.update_activity(act_obj.id, e_nom, e_pro, e_ins, g_val, o_val, rubric_opts[e_rub], frase_opts[e_fra], e_recs_ids)
                            st.success("Actividad actualizada correctamente."); st.rerun()
                        if c2.form_submit_button("Eliminar Actividad"):
                            self.db.delete_activity(act_obj.id); st.rerun()

    def tab_ai_config(self) -> None:
        st.subheader("👤 Perfil del Asesor")
        dirs = self.db.get_all_directrices()
        
        with st.form("form_perfil_y_prompts"):
            c1, c2 = st.columns(2)
            d_nombre = c1.text_input("Nombre Completo (Firma)", dirs.get("asesor_nombre", ""))
            d_rol = c2.text_input("Puesto / Rol", dirs.get("asesor_rol", ""))
            c3, c4 = st.columns(2)
            d_id = c3.text_input("ID / Matrícula", dirs.get("asesor_id", ""))
            d_grupo = c4.text_input("Grupo asignado actual", dirs.get("grupo", ""))
            
            st.markdown("---")
            st.subheader("🧠 Instrucciones del Sistema (Prompt Builder)")
            st.caption("Configura el comportamiento base de la Inteligencia Artificial. Las etiquetas {asesor_nombre} y {asesor_rol} se reemplazarán automáticamente.")
            d_sistema = st.text_area("Rol de la IA (System Prompt)", dirs.get("prompt_sistema", ""), height=70)
            d_formato = st.text_area("Reglas de Formato Estrictas", dirs.get("reglas_formato", ""), height=70)
            
            st.markdown("---")
            st.subheader("📏 Directrices Pedagógicas por Sección")
            st.caption("Controla la redacción específica de cada bloque en las retroalimentaciones.")
            d_saludo = st.text_area("1. Saludo", dirs.get("saludo", ""), height=70)
            d_fortalezas = st.text_area("2. Fortalezas", dirs.get("fortalezas", ""), height=70)
            d_areas = st.text_area("3. Áreas de oportunidad", dirs.get("areas_oportunidad", ""), height=70)
            d_sugerencias = st.text_area("4. Sugerencias", dirs.get("sugerencias", ""), height=70)
            d_recursos = st.text_area("5. Recursos de apoyo", dirs.get("recursos_apoyo", ""), height=70)
            d_despedida = st.text_area("6. Despedida", dirs.get("despedida", ""), height=70)
            d_firma = st.text_input("7. Frase de cortesía final (Ej. Cordialmente.)", dirs.get("firma", "Cordialmente."))
            
            if st.form_submit_button("Guardar Perfil e Instrucciones", type="primary", use_container_width=True):
                self.db.update_directriz("asesor_nombre", d_nombre)
                self.db.update_directriz("asesor_rol", d_rol)
                self.db.update_directriz("asesor_id", d_id)
                self.db.update_directriz("grupo", d_grupo)
                self.db.update_directriz("prompt_sistema", d_sistema)
                self.db.update_directriz("reglas_formato", d_formato)
                self.db.update_directriz("saludo", d_saludo)
                self.db.update_directriz("fortalezas", d_fortalezas)
                self.db.update_directriz("areas_oportunidad", d_areas)
                self.db.update_directriz("sugerencias", d_sugerencias)
                self.db.update_directriz("recursos_apoyo", d_recursos)
                self.db.update_directriz("despedida", d_despedida)
                self.db.update_directriz("firma", d_firma)
                st.success("¡Perfil, System Prompts y Directrices actualizados con éxito!")
                st.rerun()

    def tab_settings(self) -> None:
        st.subheader("🔑 Clave de API Global")
        st.session_state.api_key = st.text_input("Clave de API OpenRouter", st.session_state.api_key, type="password")
        
        if st.button("Probar conexión con API", width="stretch"):
            ok, msg = self.ia_client.probar_conexion(st.session_state.api_key, "cohere/north-mini-code:free")
            st.success(msg) if ok else st.error(msg)
            
        st.markdown("---")
        st.subheader("🤖 Catálogo de Modelos de IA")
        st.caption("Administra tu propio portafolio de modelos. Los modelos marcados como 'Gratis' se usarán como salvavidas automáticos si el principal falla.")
        
        with st.form("form_add_modelo"):
            st.markdown("**Agregar Nuevo Modelo**")
            col1, col2, col3 = st.columns(3)
            m_nom = col1.text_input("Nombre a mostrar (Ej. GPT-4o)")
            m_api = col2.text_input("ID en OpenRouter (Ej. openai/gpt-4o)")
            m_cat = col3.selectbox("Categoría", ["Gratis", "De pago"])
            
            if st.form_submit_button("Guardar Modelo"):
                if m_nom and m_api:
                    try:
                        self.db.create_modelo(m_nom, m_api, m_cat)
                        st.success("Modelo agregado correctamente.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error (¿El ID ya existe?): {e}")
                else:
                    st.error("El nombre y el ID de OpenRouter son obligatorios.")

        st.markdown("#### Modelos Configurados")
        for m in self.db.get_modelos():
            with st.expander(f"{m['nombre']} ({m['categoria']}) — {m['api_id']}"):
                if st.button("🗑️ Eliminar modelo", key=f"del_mod_{m['id']}"):
                    self.db.delete_modelo(m['id'])
                    st.rerun()
            
        st.markdown("---")
        st.subheader("💾 Base de datos")
        c1, c2 = st.columns(2)
        if c1.button("Crear respaldo", width="stretch"):
            path = self.db.backup()
            st.success(f"Respaldo: {path.name}")
            
        data = self.db.export_all_json()
        c2.download_button("Exportar BD JSON", json.dumps(data, ensure_ascii=False, indent=2), "retro_export.json", "application/json", width="stretch")

        # --- SECCIÓN DE LOGS DE EVENTOS DESDE LA BASE DE DATOS ---
        st.markdown("---")
        st.subheader("📝 Registro de Eventos (Caja Negra del Bot)")
        st.caption("Revisa los procesos internos, errores de conexión y tiempos de espera desde Heroku.")
        
        logs = self.db.get_logs(limit=100)
        if logs:
            log_text = "\n".join([f"[{l['fecha']}] {l['nivel']}: {l['mensaje']}" for l in reversed(logs)])
            st.text_area("Últimos 100 eventos:", value=log_text, height=250)
            if st.button("🗑️ Limpiar Logs", width="stretch"):
                self.db.clear_logs()
                st.rerun()
        else:
            st.info("No hay eventos registrados todavía (Usa el bot para empezar a ver los registros).")

    def tab_forums(self) -> None:
        """Pestaña para la generación automatizada de aportaciones a Foros Aprendiendo."""
        st.header("💬 Generador de Aportaciones: Foro Aprendiendo")
        st.markdown("Automatiza tus participaciones diarias manteniendo tu estilo y cumpliendo con los lineamientos de Prepa en Línea-SEP.")
        
        col1, col2 = st.columns(2)
        with col1:
            semana = st.selectbox("Semana del Módulo:", ["Semana 1", "Semana 2", "Semana 3", "Semana 4"])
        with col2:
            dia = st.selectbox("Día de participación:", [
                "Lunes (Apertura y Planteamiento)", 
                "Martes (Interacción y Retroalimentación)", 
                "Miércoles (Ortografía y Redacción)", 
                "Jueves (Orientación Matemática)", 
                "Viernes (Cierre de semana)"
            ])
            
        tono = st.selectbox("Variación de estilo (Para no repetir):", [
            "Estándar (Versión A)", 
            "Empático y Motivador (Versión B)", 
            "Directo y Académico (Versión C)"
        ])
        
        if st.button("✨ Generar Aportación Automática", type="primary", width="stretch"):
            dirs = self.db.get_all_directrices()
            n_ase = dirs.get("asesor_nombre", "Asesor")
            r_ase = dirs.get("asesor_rol", "Asesor virtual")
            id_ase = dirs.get("asesor_id", "000000")
            g_ase = dirs.get("grupo", "M00C0G00-000")

            temas = {
                "Semana 1": "Razones y proporciones. Problema detonador: Luis viajó 600 km y gastó 85 litros. ¿Cuántos litros para 870 km?",
                "Semana 2": "Lenguaje común y algebraico. Problema detonador: Jardinero, campo de futbol de 14m de largo. Superficie es b. Expresar el ancho.",
                "Semana 3": "Sistemas de ecuaciones. Problema detonador: Galería de arte contrata pintor. Paquete 1: 2 lienzos, 4 pinceles por $320. Paquete 2: 1 lienzo, 3 pinceles por $180.",
                "Semana 4": "Ecuaciones cuadráticas. Problema detonador: Empresa de lámparas gana $84. Si ganara $1 menos al día, trabajaría 2 días más."
            }
            
            instrucciones_dia = {
                "Lunes (Apertura y Planteamiento)": "Explica el propósito de la semana, la dinámica del foro, las reglas de participación e invita a resolver el problema detonador.",
                "Martes (Interacción y Retroalimentación)": "Fomenta que revisen los comentarios de los demás, promueve el debate, la interacción entre pares y da ánimos.",
                "Miércoles (Ortografía y Redacción)": "Haz un comentario sutil pero formal fomentando las buenas prácticas de redacción, uso de tildes o evitar pleonasmos como consejo para sus participaciones.",
                "Jueves (Orientación Matemática)": "Da una pista técnica o matemática sin resolverles el problema completo. Orienta sobre cómo plantear las ecuaciones, fórmulas o el despeje.",
                "Viernes (Cierre de semana)": "Concluye el foro de esta semana, agradece las participaciones, reflexiona sobre la utilidad del tema en la vida real e invita a aprovechar el fin de semana."
            }
            
            prompt = f"""
            Eres {n_ase}, {r_ase} (Grupo {g_ase}).
            Necesito que redactes mi aportación diaria para el "Foro Aprendiendo".
            
            Contexto del módulo actual:
            Tema central: {temas[semana]}
            Día de la semana: {dia}. Instrucción estricta para el mensaje de hoy: {instrucciones_dia[dia]}
            Tono solicitado para dar variedad: {tono}
            
            Reglas estrictas de redacción (basado en mi banco de datos histórico):
            1. Saludo inicial: "Apreciables estudiantes." (Debe ir en una línea separada al inicio).
            2. Despedida obligatoria (Al final del mensaje, tal cual esto):
            {n_ase}
            {r_ase}
            {id_ase}
            {g_ase}
            3. Escribe en español de México, formal pero cálido y empático. Sin muletillas, con excelente ortografía.
            4. No pongas formato Markdown de títulos grandes (##) ni "Asunto:". El texto debe verse natural, listo para copiar y pegar en un foro de Moodle. Usa negritas solo si es estrictamente necesario para resaltar una pista matemática.
            """
            
            with st.spinner("⏳ Redactando tu participación para el foro..."):
                try:
                    respuesta = self.ia_client.generar(prompt, st.session_state.api_key, st.session_state.model_id, st.session_state.temperature, 1500)
                    st.success("¡Aportación generada con éxito!")
                    st.text_area("Copia y pega este texto directamente en Moodle:", value=respuesta, height=400)
                except Exception as e:
                    st.error(f"Error al generar la aportación: {e}")
