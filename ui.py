"""Interfaz Streamlit con módulos de edición integrados."""
from __future__ import annotations

import json
import os
from datetime import date
from types import SimpleNamespace
from typing import Any

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from config import (
    APP_ICON, APP_LAYOUT, APP_TITLE, DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL_ID, DEFAULT_MODEL_NAME, DEFAULT_TEMPERATURE,
)
from database import DatabaseManager
from ia_client import IAClient
from models import Retroalimentacion
from prompt_builder import PromptBuilder
from styles import app_css
from ui_components import (
    activity_form, download_buttons, evaluation_inputs, frase_global_form,
    header, history_card, recurso_global_form, rubric_import_form, rubric_manual_form,
)
from utils import (
    create_zip, docx_bytes, feedback_to_moodle_html, generar_nombre_archivo,
    get_activity_code, pdf_bytes,
)


class RetroalimentacionApp:
    def __init__(self, db: DatabaseManager) -> None:
        self.db = db
        self.ia_client = IAClient("openrouter")

    def run(self) -> None:
        load_dotenv()
        st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout=APP_LAYOUT)
        st.markdown(app_css(), unsafe_allow_html=True)
        self._state()

        dirs_cache = self.db.get_all_directrices()
        nombre_asesor = (dirs_cache.get("asesor_nombre") or "Asesor").split()[0]

        routes = {
            "🏠 1. Generar retroalimentación": self.tab_generate,
            "📜 2. Historial y Lotes": self.tab_history,
            "📋 3. Configuración de actividades": self.tab_activities,
            "🤖 4. Configuración IA y Perfil": self.tab_ai_config,
            "⚙️ 5. Configuración del Sistema": self.tab_settings,
            "💬 6. Generador de Foros": self.tab_forums,
        }

        with st.sidebar:
            st.markdown(f"### {nombre_asesor}")
            if st.button("Cerrar sesión", width="stretch"):
                st.info("Sesión cerrada (Simulación)")
            st.markdown("---\n📄 Sin documento activo\n---\n")
            st.caption("Flujo de trabajo")
            pagina_actual = st.radio("Navegación", list(routes.keys()), label_visibility="collapsed")

        header()
        routes[pagina_actual]()
        st.markdown("<br><hr><center><small class='small-muted'>Retroalimentaciones Formativas IA</small></center>", unsafe_allow_html=True)

    def _state(self) -> None:
        defaults = {
            "api_key": os.getenv("OPENROUTER_API_KEY", ""),
            "model_name": DEFAULT_MODEL_NAME,
            "model_id": DEFAULT_MODEL_ID,
            "temperature": DEFAULT_TEMPERATURE,
            "max_tokens": DEFAULT_MAX_TOKENS,
            "last_feedback": "", "last_prompt": "",
            "last_feedback_student": "", "last_feedback_activity": "",
            "batch_queue": [],
        }
        for k, v in defaults.items():
            st.session_state.setdefault(k, v)

    def _get_model_name(self, model_id: str) -> str:
        return next((m["nombre"] for m in self.db.get_modelos() if m.get("api_id") == model_id), st.session_state.model_name)

    def _get_model_for_format_error(self, selected_model_id: str, modelos: list[dict[str, Any]]) -> str | None:
        selected_model_id = str(selected_model_id or "").strip()
        if "haiku" not in selected_model_id.lower():
            return selected_model_id or None
        return next((str(m["api_id"]).strip() for m in modelos if m.get("api_id") and "haiku" not in str(m["api_id"]).lower()), None)

    def _clear_last_feedback(self) -> None:
        for k in ["last_feedback", "last_prompt", "last_feedback_student", "last_feedback_activity"]:
            st.session_state[k] = ""

    def _persist_retro(self, builder: PromptBuilder, act_id: int | None, act_nombre: str, text: str, model_id: str, prompt: str) -> None:
        item = Retroalimentacion(
            estudiante=builder.estudiante,
            actividad=act_nombre,
            texto_generado=text,
            modelo_usado=self._get_model_name(model_id),
            calificacion=builder.calificacion,
            criterios=builder.criterios_evaluados,
            observaciones=builder.observaciones,
            prompt=prompt,
            temperatura=st.session_state.temperature,
        )
        self.db.create_history(item, act_id)

    def tab_generate(self) -> None:
        activities = self.db.list_activities()
        if not activities:
            st.warning("Primero registra una actividad en la Configuración de Actividades.")
            return

        labels = {r["nombre"]: r["id"] for r in activities}
        modo = st.radio("Modo de Evaluación", ["👤 Individual", "📦 Lote (Batch)"], horizontal=True)
        st.markdown("---")

        selected = st.selectbox("Selecciona la Actividad a evaluar", list(labels.keys()))
        activity = self.db.get_activity(labels[selected])
        modelos = self.db.get_modelos()

        if not activity or not modelos:
            if not modelos:
                st.error("No hay modelos configurados. Ve a 'Configuración del Sistema' para agregar uno.")
            return

        with st.expander("🤖 Configuración del Modelo de IA (Despliega para cambiar)", expanded=False):
            c1, c2, c3 = st.columns([2, 1, 1])
            opts_modelos = {f"{m['nombre']} ({m['categoria']})": m for m in modelos}
            idx_mod = next((i for i, k in enumerate(opts_modelos) if opts_modelos[k]["api_id"] == st.session_state.model_id), 0)
            sel_nombre = c1.selectbox("Modelo", list(opts_modelos.keys()), index=idx_mod)
            st.session_state.model_name = opts_modelos[sel_nombre]["nombre"]
            st.session_state.model_id = opts_modelos[sel_nombre]["api_id"]
            st.session_state.temperature = c2.slider("Temperatura", 0.0, 1.5, float(st.session_state.temperature), 0.1)
            st.session_state.max_tokens = c3.slider("Tokens (Max)", 200, 8000, int(st.session_state.max_tokens), 100)

        with st.form("evaluacion_form"):
            st.markdown("### 📝 Datos de la Evaluación")
            estudiante = st.text_input("Nombre del Estudiante", placeholder="Ej. Argelia")
            criterios, calif = evaluation_inputs(activity.nombre)
            tipo_obs = st.radio("¿Deseas agregar observaciones manuales?", ["❌ No, generar directo", "📝 Sí, escribir nota al estudiante"], horizontal=True)
            formato_err = st.checkbox("⚠️ Evaluar por formato incorrecto", help="Genera retroalimentación corta sin rúbrica.")
            obs = st.text_area("Escribe tus observaciones (o error de formato si aplica):", height=100)
            st.markdown("---")
            btn_label = "✨ Generar Retroalimentación" if modo == "👤 Individual" else "➕ Agregar a la cola de procesamiento"
            submit_eval = st.form_submit_button(btn_label, type="primary", use_container_width=True)

        if submit_eval:
            self._clear_last_feedback()

            if formato_err:
                texto_base = (
                    obs.strip()
                    or "Entregó en un formato equivocado."
                )
            elif tipo_obs == "📝 Sí, escribir nota al estudiante":
                texto_base = obs.strip()
            else:
                texto_base = ""

            builder = PromptBuilder(
                directrices=self.db.get_all_directrices(), actividad=activity, estudiante=estudiante,
                calificacion=calif, criterios_evaluados=criterios, observaciones=texto_base, es_error_formato=formato_err,
            )
            if modo == "👤 Individual":
                modelo_usar = self._get_model_for_format_error(st.session_state.model_id, modelos) if formato_err else st.session_state.model_id
                if not modelo_usar:
                    st.error("No hay un modelo disponible para procesar el error de formato.")
                    return
                if formato_err and modelo_usar != st.session_state.model_id:
                    st.warning("⚠️ Haiku excluido temporalmente. Se usará un modelo alternativo.")
                self._generate_feedback(builder, activity.id, modelo_usar)
            else:
                val = builder.validate()
                if val.ok:
                    st.session_state.batch_queue.append({
                        "estudiante": estudiante, "calificacion_total": calif,
                        "criterios_evaluados": criterios, "observaciones": texto_base, "es_error_formato": formato_err,
                    })
                    st.success(f"✅ {estudiante} agregado a la cola de procesamiento.")
                else:
                    for err in val.errors:
                        st.error(err)

        if modo == "👤 Individual":
            if st.session_state.last_feedback and st.session_state.last_feedback_student == estudiante.strip() and st.session_state.last_feedback_activity == activity.nombre:
                dirs = self.db.get_all_directrices()
                n_ase, id_ase = dirs.get("asesor_nombre", ""), dirs.get("asesor_id", "")
                title = generar_nombre_archivo(estudiante, activity.nombre)
                html_fb = feedback_to_moodle_html(st.session_state.last_feedback, n_ase, id_ase)

                st.subheader("Resultado")
                if "foro de integración" in activity.nombre.lower():
                    st.info(f"🔢 **Calificación para Moodle:** `{calif:.1f} / 100`")
                st.markdown(st.session_state.last_feedback)

                with st.expander("📋 HTML compacto para Moodle"):
                    st.text_area("Código HTML", value=html_fb, height=220, key="html_feedback_moodle")

                payload = json.dumps({"retroalimentacion": st.session_state.last_feedback, "prompt": st.session_state.last_prompt}, ensure_ascii=False, indent=2)
                download_buttons(title, st.session_state.last_feedback, html_fb, docx_bytes("", st.session_state.last_feedback, n_ase, id_ase), pdf_bytes("", st.session_state.last_feedback), payload)
        elif st.session_state.batch_queue:
            st.markdown("### 📋 Cola de Procesamiento")
            for idx, item in enumerate(st.session_state.batch_queue):
                st.write(f"{idx + 1}. **{item['estudiante']}** ({item['calificacion_total']} pts)")

            if st.button("🚀 Procesar todo el lote ahora", type="primary"):
                p_bar, total_q = st.progress(0), len(st.session_state.batch_queue)
                mods = self.db.get_modelos()

                for idx, item in enumerate(st.session_state.batch_queue):
                    b_lote = PromptBuilder(
                        directrices=self.db.get_all_directrices(), actividad=activity, estudiante=item["estudiante"],
                        calificacion=item["calificacion_total"], criterios_evaluados=item["criterios_evaluados"],
                        observaciones=item["observaciones"], es_error_formato=item.get("es_error_formato", False),
                    )
                    prompt = b_lote.build()
                    mod_usar = self._get_model_for_format_error(st.session_state.model_id, mods) if item.get("es_error_formato") else st.session_state.model_id

                    if not mod_usar:
                        st.error(f"Sin modelo alternativo para {item['estudiante']}. Omitido.")
                        p_bar.progress((idx + 1) / total_q)
                        continue

                    try:
                        text = self.ia_client.generar(prompt, st.session_state.api_key, mod_usar, st.session_state.temperature, st.session_state.max_tokens)
                        self._persist_retro(b_lote, activity.id, activity.nombre, text, mod_usar, prompt)
                    except Exception as exc:
                        st.error(f"Error con {item['estudiante']}: {exc}")
                    p_bar.progress((idx + 1) / total_q)

                st.session_state.batch_queue.clear()
                st.success("✨ ¡Lote generado exitosamente! Descárgalo en 'Historial'.")

    def _generate_feedback(self, builder: PromptBuilder, activity_id: int | None, modelo_override: str | None = None) -> None:
        validation = builder.validate()
        for err in validation.errors:
            st.error(err)
        if not validation.ok:
            return

        try:
            with st.spinner("Generando redacción pedagógica original..."):
                prompt = builder.build()
                modelo = modelo_override or st.session_state.model_id
                text = self.ia_client.generar(prompt, st.session_state.api_key, modelo, st.session_state.temperature, st.session_state.max_tokens)

            st.session_state.last_feedback = text
            st.session_state.last_prompt = prompt
            st.session_state.last_feedback_student = builder.estudiante
            st.session_state.last_feedback_activity = builder.actividad.nombre if builder.actividad else ""

            self._persist_retro(builder, activity_id, st.session_state.last_feedback_activity, text, modelo, prompt)
            st.success("Guardado en el historial.")
        except Exception as exc:
            st.error(f"Error: {exc}")

    def tab_history(self) -> None:
        st.subheader("📦 Descarga y Gestión de Evaluaciones por Lote")
        lista_act = self.db.list_activities()
        activities = {"Todas": None, **{r["nombre"]: r["id"] for r in lista_act}}
        act_map = {r["id"]: r["nombre"] for r in lista_act}

        c1, c2 = st.columns(2)
        query = c1.text_input("🔍 Buscar en historial (Estudiante):")
        selected_act_name = c2.selectbox("Filtrar por actividad", list(activities.keys()))

        c3, c4 = st.columns(2)
        fecha_desde = c3.date_input("Fecha desde:", value=date(2026, 8, 1))
        fecha_hasta = c4.date_input("Fecha hasta:", value=date.today())

        rows = self.db.list_history(estudiante=query, actividad_id=activities[selected_act_name], limit=500,
                                    fecha_inicio=fecha_desde.strftime("%Y-%m-%d"), fecha_fin=fecha_hasta.strftime("%Y-%m-%d"))
        if not rows:
            st.info("No hay registros en esas fechas.")
            return

        st.caption(f"Registros encontrados: {len(rows)}")
        with st.expander("📦 Herramienta de Descarga en Lote (ZIP)", expanded=False):
            st.markdown("Selecciona las retroalimentaciones que deseas incluir en el archivo ZIP.")
            st.session_state.setdefault("select_all", False)

            b1, b2 = st.columns(2)
            if b1.button("✅ Seleccionar todos", width="stretch"):
                st.session_state.select_all = True
                st.rerun()
            if b2.button("⬜ Deseleccionar todos", width="stretch"):
                st.session_state.select_all = False
                st.rerun()

            df_data = [{"Seleccionar": st.session_state.select_all, "Fecha": r.get("fecha", ""), "Estudiante": r.get("estudiante", ""),
                        "Calificación": r.get("calificacion", 0.0), "ID": r.get("id", 0)} for r in rows]
            edited_df = st.data_editor(pd.DataFrame(df_data), hide_index=True, disabled=["Fecha", "Estudiante", "Calificación", "ID"], width="stretch")

            dirs = self.db.get_all_directrices()
            n_ase, id_ase = dirs.get("asesor_nombre", ""), dirs.get("asesor_id", "")
            grupo_zip = st.text_input("Grupo (para nombrar el archivo ZIP)", value=dirs.get("grupo", "M00C0G00-000"))

            selected_ids = set(edited_df[edited_df["Seleccionar"]]["ID"])
            selected_rows = [r for r in rows if r.get("id", 0) in selected_ids]

            if st.button(f"📥 Descargar {len(selected_rows)} archivos en ZIP", type="primary", disabled=not selected_rows, width="stretch"):
                archivos = []
                for r in selected_rows:
                    est = r.get("estudiante", "")
                    act_nom = act_map.get(r.get("actividad_id"), r.get("actividad_nombre") or r.get("actividad") or "General")
                    base = generar_nombre_archivo(est, act_nom)
                    fb = r.get("retroalimentacion", "")
                    archivos.extend([
                        (f"{base}.docx", docx_bytes("", fb, n_ase, id_ase)),
                        (f"{base}.html", feedback_to_moodle_html(fb, n_ase, id_ase).encode("utf-8")),
                    ])

                act_str = get_activity_code(selected_act_name) if selected_act_name != "Todas" else "Varias"
                st.download_button("💾 Guardar archivo ZIP", data=create_zip(archivos), file_name=f"Retros_{grupo_zip}_{act_str}.zip", mime="application/zip", width="stretch")

        st.markdown("---")
        for row in rows:
            history_card(row, act_map)

    def tab_activities(self) -> None:
        t1, t2, t3, t4 = st.tabs(["📚 Banco de Recursos", "✍️ Banco de Frases", "📐 Rúbricas", "🔗 Ensamblar Actividad"])

        with t1:
            st.subheader("Catálogo Global de Recursos")
            rec, sub_rec = recurso_global_form()
            if sub_rec and getattr(rec, "titulo", ""):
                self.db.create_recurso(rec)
                st.success("Recurso guardado.")
                st.rerun()

            st.markdown("---\n#### Recursos Guardados (Editar o Eliminar)")
            tipos = ["Video", "Artículo", "Enlace", "PDF", "Otro"]
            for r in self.db.list_recursos_globales():
                r_tit, r_tip = getattr(r, "titulo", ""), getattr(r, "tipo", "Video")
                with st.expander(f"📌 {r_tit} [{r_tip}]"):
                    with st.form(f"form_edit_rec_{r.id}"):
                        e_tit = st.text_input("Título", r_tit)
                        e_tip = st.selectbox("Tipo", tipos, index=tipos.index(r_tip) if r_tip in tipos else 0)
                        e_url = st.text_input("URL", getattr(r, "url", ""))
                        e_des = st.text_area("Descripción", getattr(r, "descripcion", ""), height=60)
                        c1, c2 = st.columns(2)
                        if c1.form_submit_button("Actualizar Recurso"):
                            self.db.update_recurso(r.id, SimpleNamespace(tipo=e_tip, titulo=e_tit, url=e_url, descripcion=e_des))
                            st.success("Recurso actualizado.")
                            st.rerun()
                        if c2.form_submit_button("Eliminar Recurso"):
                            self.db.delete_recurso(r.id)
                            st.rerun()

        with t2:
            st.subheader("Catálogo Global de Frases Célebres")
            frase, sub_fra = frase_global_form()
            if sub_fra and getattr(frase, "texto", ""):
                self.db.create_frase(frase.texto, frase.autor)
                st.success("Frase guardada.")
                st.rerun()

            st.markdown("---\n#### Frases Guardadas (Editar o Eliminar)")
            for f in self.db.list_frases():
                f_txt, f_aut = str(getattr(f, "texto", "")), str(getattr(f, "autor", ""))
                with st.expander(f"💬 {f_aut} - {f_txt[:30]}..."):
                    with st.form(f"form_edit_fra_{f.id}"):
                        e_txt = st.text_area("Frase", f_txt, height=60)
                        e_aut = st.text_input("Autor", f_aut)
                        c1, c2 = st.columns(2)
                        if c1.form_submit_button("Actualizar Frase"):
                            self.db.update_frase(f.id, e_txt, e_aut)
                            st.success("Frase actualizada.")
                            st.rerun()
                        if c2.form_submit_button("Eliminar Frase"):
                            self.db.delete_frase(f.id)
                            st.rerun()

        with t3:
            st.subheader("Rúbricas Institucionales")
            mode = st.radio("Modo", ["Manual", "Importar tabla"], horizontal=True)
            rubrica, sub_rub = rubric_manual_form() if mode == "Manual" else rubric_import_form()
            if sub_rub and getattr(rubrica, "nombre", ""):
                try:
                    self.db.create_rubric(rubrica)
                    st.success("Rúbrica guardada.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Error: {exc}")

            st.markdown("---\n#### Rúbricas Guardadas (Editar o Eliminar)")
            for r_row in self.db.list_rubrics():
                rub_obj = self.db.get_rubric(r_row["id"])
                if not rub_obj:
                    continue
                with st.expander(r_row["nombre"]):
                    with st.form(f"form_edit_rub_{r_row['id']}"):
                        e_nom = st.text_input("Nombre de la rúbrica", getattr(rub_obj, "nombre", ""))
                        e_cont = st.text_area("Contenido base", getattr(rub_obj, "contenido", ""), height=150)
                        c1, c2 = st.columns(2)
                        if c1.form_submit_button("Actualizar"):
                            self.db.update_rubric(r_row["id"], SimpleNamespace(nombre=e_nom, contenido=e_cont))
                            st.success("Rúbrica actualizada.")
                            st.rerun()
                        if c2.form_submit_button("Eliminar"):
                            self.db.delete_rubric(r_row["id"])
                            st.rerun()

        with t4:
            st.subheader("Configurar Nueva Actividad")
            st.caption("Une la rúbrica, la frase y los recursos para crear la actividad final.")
            all_rubs, all_fra, all_recs = self.db.list_rubrics(), self.db.list_frases(), self.db.list_recursos_globales()

            act, r_id, f_id, rec_ids, sub_act = activity_form(all_rubs, all_fra, all_recs)
            if sub_act and getattr(act, "nombre", ""):
                try:
                    self.db.create_activity(act, r_id, f_id, rec_ids)
                    st.success("Actividad Ensamblada.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Error: {exc}")

            st.markdown("---\n#### Actividades Configuradas (Editar Ensamblado o Eliminar)")
            for act_raw in self.db.list_activities():
                act_obj = self.db.get_activity(act_raw["id"])
                if not act_obj:
                    continue

                with st.expander(f"⚙️ Editar: {getattr(act_obj, 'nombre', '')}"):
                    with st.form(f"form_edit_act_{act_obj.id}"):
                        e_nom = st.text_input("Nombre de la actividad", getattr(act_obj, "nombre", ""))
                        e_pro = st.text_area("Propósito de la actividad", getattr(act_obj, "proposito", ""), height=60)
                        e_ins = st.text_area("Instrucciones detalladas", getattr(act_obj, "instrucciones", ""), height=90)

                        rub_id = getattr(getattr(act_obj, "rubrica", None), "id", None)
                        fra_id = getattr(getattr(act_obj, "frase", None), "id", None)

                        rub_opts = {"Sin rúbrica": None, **{row["nombre"]: row["id"] for row in all_rubs}}
                        fra_opts = {"Sin frase": None, **{f'"{getattr(f, "texto", "")[:40]}..." - {getattr(f, "autor", "")}': f.id for f in all_fra}}
                        rec_opts = {getattr(r, "titulo", ""): r.id for r in all_recs}
                        curr_recs = [getattr(r, "titulo", "") for r in getattr(act_obj, "recursos", []) if getattr(r, "titulo", "") in rec_opts]

                        c1, c2 = st.columns(2)
                        r_vals, f_vals = list(rub_opts.values()), list(fra_opts.values())
                        e_rub = c1.selectbox("Rúbrica asociada", list(rub_opts.keys()), index=r_vals.index(rub_id) if rub_id in r_vals else 0)
                        e_fra = c2.selectbox("Frase de cierre asociada", list(fra_opts.keys()), index=f_vals.index(fra_id) if fra_id in f_vals else 0)
                        e_recs = st.multiselect("Recursos asociados", list(rec_opts.keys()), default=curr_recs)

                        col1, col2 = st.columns(2)
                        if col1.form_submit_button("Actualizar Ensamblado"):
                            grupo = getattr(act_obj, "grupo", "M00C0G00-000")
                            orden = getattr(act_obj, "orden", 0)
                            self.db.update_activity(act_obj.id, e_nom, e_pro, e_ins, grupo, orden, rub_opts[e_rub], fra_opts[e_fra], [rec_opts[n] for n in e_recs])
                            st.success("Actividad actualizada correctamente.")
                            st.rerun()
                        if col2.form_submit_button("Eliminar Actividad"):
                            self.db.delete_activity(act_obj.id)
                            st.rerun()

    def tab_ai_config(self) -> None:
        st.subheader("👤 Perfil del Asesor")
        dirs = self.db.get_all_directrices()

        with st.form("form_perfil_y_prompts"):
            c1, c2 = st.columns(2)
            d_nom = c1.text_input("Nombre Completo (Firma)", dirs.get("asesor_nombre", ""))
            d_rol = c2.text_input("Puesto / Rol", dirs.get("asesor_rol", ""))
            c3, c4 = st.columns(2)
            d_id = c3.text_input("ID / Matrícula", dirs.get("asesor_id", ""))
            d_grp = c4.text_input("Grupo asignado actual", dirs.get("grupo", ""))

            st.markdown("---\n### 🧠 Instrucciones del Sistema (Prompt Builder)")
            st.caption("Configura el comportamiento base de la IA. Las etiquetas {asesor_nombre} y {asesor_rol} se reemplazarán automáticamente.")

            fields = [
                ("prompt_sistema", "Rol de la IA (System Prompt)", 70),
                ("reglas_formato", "Reglas de Formato Estrictas", 70),
                ("error_formato", "Instrucción para Error de Formato", 70),
                ("saludo", "1. Saludo", 70),
                ("fortalezas", "2. Fortalezas", 70),
                ("areas_oportunidad", "3. Áreas de oportunidad", 70),
                ("sugerencias", "4. Sugerencias", 70),
                ("recursos_apoyo", "5. Recursos de apoyo", 70),
                ("despedida", "6. Despedida", 70),
            ]
            inputs = {"asesor_nombre": d_nom, "asesor_rol": d_rol, "asesor_id": d_id, "grupo": d_grp}
            for key, label, h in fields:
                val = dirs.get(key, "La actividad se evalúa con calificación mínima por no cumplir formato." if key == "error_formato" else "")
                inputs[key] = st.text_area(label, val, height=h)

            inputs["firma"] = st.text_input("7. Frase de cortesía final (Ej. Cordialmente.)", dirs.get("firma", "Cordialmente."))

            if st.form_submit_button("Guardar Perfil e Instrucciones", type="primary", use_container_width=True):
                for k, v in inputs.items():
                    self.db.update_directriz(k, v)
                st.success("¡Perfil, System Prompts y Directrices actualizados con éxito!")
                st.rerun()

    def tab_settings(self) -> None:
        st.subheader("🔑 Clave de API Global")
        st.session_state.api_key = st.text_input("Clave de API OpenRouter", st.session_state.api_key, type="password")

        if st.button("Probar conexión con API", width="stretch"):
            ok, msg = self.ia_client.probar_conexion(st.session_state.api_key, "cohere/north-mini-code:free")
            (st.success if ok else st.error)(msg)

        st.markdown("---\n### 🤖 Catálogo de Modelos de IA")
        st.caption("Administra tu propio portafolio de modelos. Los modelos 'Gratis' se usan como salvavidas si el principal falla.")

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
                    except Exception as exc:
                        st.error(f"Error (¿El ID ya existe?): {exc}")
                else:
                    st.error("El nombre y el ID de OpenRouter son obligatorios.")

        st.markdown("#### Modelos Configurados")
        for modelo in self.db.get_modelos():
            with st.expander(f"{modelo['nombre']} ({modelo['categoria']}) — {modelo['api_id']}"):
                if st.button("🗑️ Eliminar modelo", key=f"del_mod_{modelo['id']}"):
                    self.db.delete_modelo(modelo["id"])
                    st.rerun()

        st.markdown("---\n### 💾 Base de datos")
        c1, c2 = st.columns(2)
        if c1.button("Crear respaldo", width="stretch"):
            st.success(f"Respaldo: {self.db.backup().name}")
        c2.download_button("Exportar BD JSON", json.dumps(self.db.export_all_json(), ensure_ascii=False, indent=2), "retro_export.json", "application/json", width="stretch")

        st.markdown("---\n### 📝 Registro de Eventos (Caja Negra del Bot)")
        logs = self.db.get_logs(limit=100)
        if logs:
            st.text_area("Últimos 100 eventos:", value="\n".join(f"[{l['fecha']}] {l['nivel']}: {l['mensaje']}" for l in reversed(logs)), height=250)
            if st.button("🗑️ Limpiar Logs", width="stretch"):
                self.db.clear_logs()
                st.rerun()
        else:
            st.info("No hay eventos registrados todavía.")

    def tab_forums(self) -> None:
        st.header("💬 Generador de Aportaciones: Foro Aprendiendo")
        st.markdown("Automatiza tus participaciones diarias manteniendo tu estilo y cumpliendo lineamientos.")

        col1, col2 = st.columns(2)
        semana = col1.selectbox("Semana del Módulo:", ["Semana 1", "Semana 2", "Semana 3", "Semana 4"])
        dia = col2.selectbox("Día de participación:", [
            "Lunes (Apertura y Planteamiento)", "Martes (Interacción y Retroalimentación)",
            "Miércoles (Ortografía y Redacción)", "Jueves (Orientación Matemática)", "Viernes (Cierre de semana)",
        ])
        tono = st.selectbox("Variación de estilo (Para no repetir):", [
            "Estándar (Versión A)", "Empático y Motivador (Versión B)", "Directo y Académico (Versión C)",
        ])

        if st.button("✨ Generar Aportación Automática", type="primary", width="stretch"):
            dirs = self.db.get_all_directrices()
            n_ase = dirs.get("asesor_nombre", "Asesor")
            r_ase = dirs.get("asesor_rol", "Asesor virtual")
            id_ase = dirs.get("asesor_id", "000000")
            g_ase = dirs.get("grupo", "M00C0G00-000")

            temas = {
                "Semana 1": "Razones y proporciones. Luis viajó 600 km y gastó 85L. ¿Litros para 870 km?",
                "Semana 2": "Lenguaje común y algebraico. Jardinero, campo 14m largo. Superficie b. Expresar ancho.",
                "Semana 3": "Sistemas de ecuaciones. Pq1: 2 lienzos, 4 pinceles por $320. Pq2: 1 lienzo, 3 pinceles por $180.",
                "Semana 4": "Ecuaciones cuadráticas. Lámparas gana $84. Si ganara $1 menos al día, trabajaría 2 días más.",
            }
            instrucciones = {
                "Lunes (Apertura y Planteamiento)": "Explica propósito, dinámica, reglas e invita al detonador.",
                "Martes (Interacción y Retroalimentación)": "Fomenta debate, interacción entre pares y anima.",
                "Miércoles (Ortografía y Redacción)": "Comenta sobre buenas prácticas de redacción y tildes.",
                "Jueves (Orientación Matemática)": "Da pista matemática sin resolver. Orienta en ecuaciones/despejes.",
                "Viernes (Cierre de semana)": "Concluye, agradece participaciones, reflexiona y despide la semana.",
            }

            prompt = (
                f"Eres {n_ase}, {r_ase} (Grupo {g_ase}). Redacta la aportación diaria para 'Foro Aprendiendo'.\n"
                f"Tema: {temas[semana]} | Día: {dia} | Instrucción: {instrucciones[dia]} | Tono: {tono}\n"
                f"Reglas: 1. Saludo: 'Apreciables estudiantes.' en línea separada.\n"
                f"2. Despedida obligatoria: {n_ase}\\n{r_ase}\\n{id_ase}\\n{g_ase}\n"
                "3. Español de México formal y empático. Sin títulos grandes (#) ni 'Asunto:'. Listo para Moodle."
            )

            with st.spinner("⏳ Redactando tu participación para el foro..."):
                try:
                    res = self.ia_client.generar(prompt, st.session_state.api_key, st.session_state.model_id, st.session_state.temperature, 1500)
                    st.success("¡Aportación generada con éxito!")
                    st.text_area("Copia y pega este texto directamente en Moodle:", value=res, height=400)
                except Exception as exc:
                    st.error(f"Error al generar la aportación: {exc}")
