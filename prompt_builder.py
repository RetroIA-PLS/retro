"""Constructor de prompts optimizado para redacción pedagógica modular, libre de código duro."""

from __future__ import annotations
import random
from typing import Any
from models import Actividad
from validators import ValidationResult


class PromptBuilder:
    def __init__(self, directrices: dict[str, str], actividad: Actividad | None, estudiante: str, calificacion: float, criterios_evaluados: dict[str, dict[str, Any]], observaciones: str, es_error_formato: bool = False) -> None:
        self.dirs = directrices
        self.actividad = actividad
        self.estudiante = estudiante.strip()
        self.calificacion = calificacion
        self.criterios_evaluados = criterios_evaluados
        self.observaciones = observaciones.strip()
        self.es_error_formato = es_error_formato

    def count_tokens(self) -> int:
        return len(self.build()) // 4

    def validate(self) -> ValidationResult:
        res = ValidationResult()
        if not self.estudiante: res.add_error("El nombre del estudiante es obligatorio.")
        if not self.actividad: res.add_error("Debes seleccionar una actividad.")
        return res

    def preview(self) -> str:
        return self.build()

    def build(self) -> str:
        act = self.actividad
        n_act = act.nombre if act else "Actividad"
        prop_act = act.proposito if act else ""
        
        # DATOS DINÁMICOS DEL ASESOR
        n_ase = self.dirs.get('asesor_nombre', 'Asesor').strip()
        r_ase = self.dirs.get('asesor_rol', 'Asesor virtual').strip()
        id_ase = self.dirs.get('asesor_id', '000000').strip()
        grupo_asignado = self.dirs.get('grupo', 'M00C0G00-000').strip()
        
        # PROMPTS DINÁMICOS DEL SISTEMA
        prompt_sistema = self.dirs.get('prompt_sistema', f'Eres un {r_ase} empático y profesional llamado {n_ase}. Debes redactar una retroalimentación ÚNICA y PERSONALIZADA. Tienes PROHIBIDO repetir estructuras sintácticas entre un estudiante y otro.')
        prompt_sistema = prompt_sistema.replace('{asesor_nombre}', n_ase).replace('{asesor_rol}', r_ase)
        
        reglas_formato = self.dirs.get('reglas_formato', 'ESTÁ ESTRICTAMENTE PROHIBIDO usar subtítulos Markdown (Ejemplo: NO escribas "## Áreas de Oportunidad"). Todo debe fluir como una carta natural, separada únicamente por saltos de párrafo.')
        
        # DESPEDIDA ALEATORIA
        firmas_base = ["Cordialmente.", "Atentamente.", "Con afecto.", "Saludos cordiales."]
        firma_personalizada = self.dirs.get('firma', '').strip()
        if firma_personalizada and firma_personalizada not in firmas_base:
            firmas_base.append(firma_personalizada)
        firma_corta = random.choice(firmas_base)
        
        # =================================================================
        # CORTOCIRCUITO: PROMPT EXCLUSIVO PARA ERROR DE FORMATO
        # =================================================================
        if self.es_error_formato:
            instruccion_error = self.dirs.get('error_formato', 'La actividad se evalúa con calificación mínima porque no cumple con el formato solicitado.')
            return f"""{prompt_sistema}

### DATOS DEL ALUMNO Y ACTIVIDAD:
- Estudiante: {self.estudiante}
- Actividad: "{n_act}"
- Detalle del error (Notas del Asesor): {self.observaciones if self.observaciones else "Entregó la actividad en un formato de archivo incorrecto."}

### INSTRUCCIÓN CRÍTICA DE FORMATO INCORRECTO:
{instruccion_error}

¡REGLA DE ORO!: TIENES ESTRICTAMENTE PROHIBIDO desglosar los criterios de la rúbrica (Cognitivo, Actitudinal, Comunicativo, etc.). No los menciones. Solo debes redactar un mensaje breve, directo y unificado (1 o 2 párrafos máximo) informando al estudiante sobre el error de formato, basándote en el "Detalle del error" proporcionado arriba.

1. **SALUDO:** Inicia EXACTAMENTE con: **Apreciable, {self.estudiante}.** (Dando un salto de línea después).
2. **CUERPO DEL MENSAJE:** Redacta la observación del error de formato con empatía pero firmeza, invitándolo a revisar las instrucciones para futuras entregas.
3. **DESPEDIDA:** Usa exactamente esta firma:
{firma_corta}

{n_ase}
{r_ase}
{id_ase}
{grupo_asignado}"""

        # =================================================================
        # FLUJO NORMAL DE ACTIVIDADES
        # =================================================================
        is_foro = "foro de integración" in n_act.lower()
        
        if act and act.frase:
            texto_frase = act.frase.texto
            autor_frase = act.frase.autor
        else:
            texto_frase = "Siempre parece imposible hasta que se hace"
            autor_frase = "Nelson Mandela"
        
        crit_str = "".join([f"{i+1}. Criterio {k}: Nivel **{v['nivel']}**.\n" for i, (k, v) in enumerate(self.criterios_evaluados.items())])
        
        rec_str = "".join([f"- {r.tipo}: {r.url} (Propósito: {r.descripcion})\n" for r in act.recursos]) if act and act.recursos else ""
        bloque_recursos = ""
        if rec_str:
            bloque_recursos = f"""
4. **RECURSOS:**
   RECUERDA: NO uses la palabra "Recursos" ni la frase "Recursos adicionales" como título. NO uses viñetas.
   {self.dirs.get('recursos_apoyo', '')}
   Redacta cada recurso en un PÁRRAFO INDEPENDIENTE usando prosa natural.
   Recursos a incluir:
{rec_str}"""

        aperturas_variadas = [
            "Es un gusto observar en tu trabajo el esfuerzo reflejado...",
            "El desarrollo de tu documento refleja un compromiso notable...",
            "Me complace revisar tu entrega, donde se aprecia un análisis...",
            "Al analizar tu actividad, es evidente la dedicación que has puesto...",
            "Quiero comenzar destacando la claridad y empeño en tu documento...",
            "Es muy grato reconocer el esfuerzo plasmado en tu entrega...",
            "Tras leer tu documento, destaco de inmediato la solidez...",
            "Tu envío demuestra un claro compromiso con tu aprendizaje...",
            "Me resulta muy interesante la manera en que abordaste los temas...",
            "Aprecio mucho el tiempo y el detalle que invertiste en esta entrega..."
        ]
        apertura_aleatoria = random.choice(aperturas_variadas)

        if is_foro:
            return f"""{prompt_sistema}

### DATOS DEL ALUMNO Y ACTIVIDAD:
- Estudiante: {self.estudiante}
- Actividad: {n_act}
- Evaluaciones (EN ORDEN ESTRICTO):
{crit_str}
- Notas específicas del Asesor: {self.observaciones if self.observaciones else "Todo correcto según los niveles."}

### REGLAS DE ORO DE FORMATO PARA EL FORO (¡MUY IMPORTANTE!):
- {reglas_formato}
- ESTÁ ESTRICTAMENTE PROHIBIDO usar subtítulos, negritas para títulos o viñetas (NO escribas "Criterio cognitivo", "Criterio actitudinal", etc.). Todo debe fluir como párrafos naturales.
- ESTÁ ESTRICTAMENTE PROHIBIDO mencionar el nombre de los niveles obtenidos (NO escribas las palabras "experto", "capacitado", "aceptable", "aprendiz", etc.). Tu trabajo es interpretar el nivel y describirlo cualitativamente.
- DISTRIBUCIÓN DE NOTAS: Si el Asesor incluyó "Notas específicas", intégralas de forma natural a lo largo de tu redacción para justificar las áreas correspondientes, no las aísles al final.

### INSTRUCCIONES ESTRICTAS DE REDACCIÓN Y SECCIONES:

1. **SALUDO Y ENTRADA:**
   Inicia exactamente con: **Apreciable, {self.estudiante}.**
   En el siguiente párrafo, escribe exactamente: "Agradezco tu participación en este foro de integración."

2. **DESARROLLO CONDENSADO (ORDEN ESTRICTO):**
   Redacta uno o dos párrafos fluidos y conversacionales integrando el desempeño del estudiante en los aspectos evaluados EXACTAMENTE EN EL MISMO ORDEN en el que se listaron arriba (Cognitivo, Actitudinal, Comunicativo, Colaborativo, Pensamiento). ¡No los revuelvas!
   Convierte los resultados de las evaluaciones en un texto cualitativo destacando sus aportaciones al foro. Utiliza tus directrices: {self.dirs.get('fortalezas', '')}

3. **ÁREAS DE OPORTUNIDAD Y SUGERENCIAS:**
   En un nuevo párrafo, menciona las áreas de mejora de forma constructiva de acuerdo con las fallas indicadas en la evaluación (si las tuvo).
   {self.dirs.get('areas_oportunidad', '')} {self.dirs.get('sugerencias', '')}

4. **CIERRE EXACTO Y DESPEDIDA:**
   Usa EXACTAMENTE esta redacción final. Solo asegúrate de copiarla tal cual:

{self.dirs.get('despedida', 'Espero que todo lo aprendido en estas cuatro semanas te sea de mucha ayuda.')}

{firma_corta}

{n_ase}
{r_ase}
{id_ase}
{grupo_asignado}"""

        else:
            return f"""{prompt_sistema}

### DATOS DEL ALUMNO Y ACTIVIDAD:
- Estudiante: {self.estudiante}
- Actividad: "{n_act}"
- Propósito de la actividad: {prop_act}
- Evaluaciones (EN ORDEN ESTRICTO):
{crit_str}
- Notas específicas del Asesor: {self.observaciones if self.observaciones else "Todo correcto según los niveles."}

### REGLAS DE ORO CONTRA ALUCINACIONES Y FORMATO (¡MUY IMPORTANTE!):
1. {reglas_formato}
2. ¡PROHIBIDO INVENTAR CONTEXTO!: Esta actividad pertenece estrictamente a un módulo de MATEMÁTICAS. Está ESTRICTAMENTE PROHIBIDO inventar conceptos de física, mecánica, diseño, historia u otras materias guiándote solo por el nombre de la actividad ("{n_act}"). Limítate a evaluar el procedimiento matemático y los datos proporcionados.
3. DISTRIBUCIÓN DE NOTAS: Las "Notas específicas del Asesor" deben ser integradas y distribuidas a lo largo de los párrafos de los criterios para justificar los niveles obtenidos. Tienes PROHIBIDO agrupar las notas del asesor en un solo párrafo aislado al final o dejarlas fuera de la carta.

### INSTRUCCIONES ESTRICTAS DE REDACCIÓN Y SECCIONES:

1. **SALUDO Y FORTALEZAS (VARIEDAD OBLIGATORIA):**
   Inicia EXACTAMENTE con: **Apreciable, {self.estudiante}.**
   ¡DEBES DAR UN SALTO DE LÍNEA DESPUÉS DEL SALUDO! (El saludo debe quedar solo en su propio renglón).
   En un NUEVO PÁRRAFO, inicia adaptando obligatoriamente esta idea: "{apertura_aleatoria}"
   Sigue esta directriz: {self.dirs.get('saludo', '')} {self.dirs.get('fortalezas', '')}
   IMPORTANTE: Al referirte al trabajo del estudiante, usa siempre el nombre de la actividad entre comillas ("{n_act}").
   ¡REGLA ESTRICTA DE APERTURA!: Tienes PROHIBIDO usar las frases "He revisado detalladamente", "He revisado con atención", o variaciones similares. 

2. **EVALUACIÓN POR CRITERIOS (ORDEN OBLIGATORIO):**
   - ORDEN ESTRICTO: Debes redactar los párrafos EXACTAMENTE en el orden en que se listaron los criterios arriba (1, 2, 3, 4). ¡Bajo ninguna circunstancia alteres la secuencia de los criterios!
   - Escribe el nombre de cada criterio en negritas EN SU PROPIO RENGLÓN AISLADO (Ejemplo:
     **Criterio cognitivo**
     [Texto del párrafo aquí abajo...]). NO uses dos puntos (:) después del título del criterio.
   - Cambia el orden en el que mencionas el nivel en los párrafos (al inicio, en medio o al final).
   - Escribe el nombre del nivel alcanzado en minúsculas y entre asteriscos dobles (ej. **experto**, **capacitado**).

3. **ÁREAS DE OPORTUNIDAD Y SUGERENCIAS:**
   Redacta en prosa fluida. RECUERDA: NO PONGAS TÍTULO A ESTA SECCIÓN.
   ¡REGLA ESTRICTA!: Tienes ESTRICTAMENTE PROHIBIDO usar frases de transición robóticas o de machote como "En cuanto a las áreas de oportunidad", "Respecto a tus áreas de mejora" o "A continuación presento las sugerencias". Pasa directamente al análisis constructivo de forma natural.
   {self.dirs.get('areas_oportunidad', '')} {self.dirs.get('sugerencias', '')}{bloque_recursos}

5. **CIERRE EXACTO Y DESPEDIDA:**
   Usa EXACTAMENTE esta redacción final. Solo asegúrate de copiarla tal cual:

{self.dirs.get('despedida', f'Para finalizar con tu retroalimentación nuevamente te felicito y agradezco el que hayas entregado tu "{n_act}".')}

Me despido con esta frase de {autor_frase}: **"{texto_frase}"**. 

Recuerda que siempre estoy para ti al otro lado de la pantalla. Me puedes contactar por medio de los canales institucionales.

{firma_corta}

{n_ase}
{r_ase}
{id_ase}
{grupo_asignado}"""
