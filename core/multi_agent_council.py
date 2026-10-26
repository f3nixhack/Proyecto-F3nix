import os
import json
import logging
from typing import Dict, List, Any, Optional, Callable
import requests

from core.memory_vault import MemoryVault
from core.fenix_reasoning import FenixReasoningEngine

logger = logging.getLogger(__name__)

# =====================================================================
# CONFIGURACIÓN DE ROLES & MODOS DE RAZONAMIENTO DIALÉCTICO F3NIX
# =====================================================================

ROLES_CONFIG = {
    # --- Roles Dialécticos Clásicos ---
    "estratega": {
        "title": "🔵 Estratega Creativo & Propositivo",
        "bg": "#121C2B",
        "border": "#1E3A5F",
        "accent": "#00B8D4",
        "badge_bg": "#0B1420",
        "system": "Diseña la mejor propuesta, plan de acción y solución práctica adaptada al 100% a la consulta."
    },
    "critico": {
        "title": "🔴 Analista Crítico & Auditor de Riesgos",
        "bg": "#251419",
        "border": "#4C1D26",
        "accent": "#FF5252",
        "badge_bg": "#190B0F",
        "system": "Examina con rigurosidad, detecta humo, puntos ciegos, costos ocultos y suposiciones poco realistas."
    },
    "director": {
        "title": "🟢 Director F3NIX (Síntesis & Plan Maestro)",
        "bg": "#10231B",
        "border": "#194833",
        "accent": "#00E676",
        "badge_bg": "#081610",
        "system": "Sintetiza el debate y formula el Plan Maestro definitivo gobernado por la Constitución Mental F3NIX."
    },
    "extractor": {
        "title": "📄 Analista de Documentos & Extracción",
        "bg": "#121A28",
        "border": "#22354E",
        "accent": "#64B5F6",
        "badge_bg": "#0D1420",
        "system": "Extrae los puntos clave, parámetros, cláusulas y datos críticos de archivos adjuntos."
    },
    "fenix": {
        "title": "👑 Comandante de Mesa",
        "bg": "#211808",
        "border": "#634710",
        "accent": "#FFB703",
        "badge_bg": "#140F05",
        "system": "Presidente de la Mesa Redonda y titular de las órdenes vinculantes."
    },

    # --- Modo Cisne Negro (Taleb Stress-Testing) ---
    "cisne_negro": {
        "title": "🦅 Auditor Cisne Negro (Chaos & Stress-Test de Taleb)",
        "bg": "#2A1724",
        "border": "#631F4F",
        "accent": "#E040FB",
        "badge_bg": "#1A0B17",
        "system": "Audita eventos improbables de impacto catastrófico para erradicar la fragilidad del plan."
    },

    # --- Modo Futuros Bifurcados (Simulación A/B) ---
    "sendero_a": {
        "title": "🅰️ Simulador Sendero A (Horizonte 3-6 Meses)",
        "bg": "#121F2B",
        "border": "#194C6D",
        "accent": "#29B6F6",
        "badge_bg": "#0C151D",
        "system": "Simula con realismo crudo el primer camino a 3 y 6 meses con costos y desgaste."
    },
    "sendero_b": {
        "title": "🅱️ Simulador Sendero B (Horizonte 3-6 Meses)",
        "bg": "#291F14",
        "border": "#68481A",
        "accent": "#FFA726",
        "badge_bg": "#181108",
        "system": "Simula con realismo crudo el camino alternativo a 3 y 6 meses con costos y desgaste."
    },

    # --- Sabios de Salud & Rendimiento ---
    "fisiologo": {
        "title": "🔵 Fisiólogo & Coach de Alto Rendimiento",
        "bg": "#10232B",
        "border": "#164B5F",
        "accent": "#26C6DA",
        "badge_bg": "#09171C",
        "system": "Diseña la periodización física, estímulo hipertrofia/fuerza y progresión semanal."
    },
    "traumatologo": {
        "title": "🔴 Traumatólogo & Especialista en Longevidad",
        "bg": "#281518",
        "border": "#5C1E26",
        "accent": "#EF5350",
        "badge_bg": "#1B0B0E",
        "system": "Protege tendones, articulaciones, sistema nervioso, descanso y nutrición antiinflamatoria."
    },

    # --- Sabios de Arquitectura & Código ---
    "arquitecto": {
        "title": "🔵 Arquitecto Clean Code & Escalabilidad",
        "bg": "#121A2C",
        "border": "#1D3766",
        "accent": "#42A5F5",
        "badge_bg": "#0B101D",
        "system": "Diseña estructuras modulares, limpias y escalables minimizando deuda técnica."
    },
    "seguridad_qa": {
        "title": "🔴 Hacker de Seguridad & Auditor QA",
        "bg": "#27141E",
        "border": "#591B3D",
        "accent": "#EC407A",
        "badge_bg": "#1A0B13",
        "system": "Busca memory leaks, condiciones de carrera, vectores de ataque y casos límite."
    },

    # --- Sabios de Vida & Filosofía ---
    "estoico": {
        "title": "🔵 Filósofo Estoico (Marco Aurelio & Séneca)",
        "bg": "#151B27",
        "border": "#273854",
        "accent": "#7E57C2",
        "badge_bg": "#0E121A",
        "system": "Analiza bajo la dicotomía de control, templanza, autodominio y fortaleza mental."
    },
    "pragmatico": {
        "title": "🔴 Pragmático Realista & Evaluador de Costos",
        "bg": "#251B12",
        "border": "#5B3A1A",
        "accent": "#FF7043",
        "badge_bg": "#170F08",
        "system": "Evalúa el costo terrenal de tiempo, fricción social, energía física y consecuencias directas."
    },

    # --- Modo Tribunal Dialéctico ---
    "defensor": {
        "title": "🔵 Abogado Defensor (Defensa de la Tesis)",
        "bg": "#121C2B",
        "border": "#1E3A5F",
        "accent": "#29B6F6",
        "badge_bg": "#0B1420",
        "system": "Defiende la validez, virtudes y legitimidad del plan con argumentos sólidos."
    },
    "fiscal": {
        "title": "🔴 Fiscal Acusador (Impugnación & Contrainterrogatorio)",
        "bg": "#291515",
        "border": "#5E1E1E",
        "accent": "#FF1744",
        "badge_bg": "#1C0A0A",
        "system": "Impugna debilidades, falsas ilusiones, contradicciones y costos ocultos."
    },

    # --- Modo Votación a Ciegas ---
    "evaluador_a": {
        "title": "🔵 Evaluador Independiente Alpha",
        "bg": "#141D2B",
        "border": "#213654",
        "accent": "#26A69A",
        "badge_bg": "#0D131C",
        "system": "Emite puntuación autónoma de viabilidad 1-10 y 3 fortalezas/riesgos clave."
    },
    "evaluador_b": {
        "title": "🟣 Evaluador Independiente Beta",
        "bg": "#22172B",
        "border": "#4F266A",
        "accent": "#AB47BC",
        "badge_bg": "#150C1B",
        "system": "Emite puntuación autónoma de viabilidad 1-10 y 3 fortalezas/riesgos clave sin ver a Alpha."
    },

    # --- Modo Socrático & Steel-Man ---
    "socratico": {
        "title": "🔍 Auditor Socrático (Interrogatorio Incisivo)",
        "bg": "#161D2B",
        "border": "#23416B",
        "accent": "#00E5FF",
        "badge_bg": "#0C131D",
        "system": "Formula exactamente 2 preguntas incisivas y trampa para desmantelar suposiciones."
    },
    "proponente": {
        "title": "🔵 Proponente Inicial del Plan",
        "bg": "#121C2B",
        "border": "#1E3A5F",
        "accent": "#00B8D4",
        "badge_bg": "#0B1420",
        "system": "Presenta el enfoque base y adapta su plan tras el proceso de blindaje."
    },
    "steelman": {
        "title": "🛡️ Auditor Steel-Man (Versión Invulnerable)",
        "bg": "#1E2614",
        "border": "#4B6122",
        "accent": "#AEEA00",
        "badge_bg": "#13190C",
        "system": "Construye la versión más sólida e inmejorable del plan antes de auditar riesgos residuales."
    }
}

DEBATE_MODES: Dict[str, Dict[str, Any]] = {
    "clasico": {
        "id": "clasico",
        "name": "🏛️ Dialéctico Clásico (Tesis, Antítesis y Síntesis)",
        "short_name": "🏛️ Clásico",
        "icon": "🏛️",
        "description": "Estratega propone soluciones, Crítico audita riesgos y Director F3NIX sintetiza el Plan Maestro.",
        "role_1": "estratega",
        "role_2": "critico",
        "role_director": "director",
        "role_1_label": "🔵 Estratega Creativo",
        "role_2_label": "🔴 Crítico de Riesgos",
        "role_director_label": "🟢 Director F3NIX"
    },
    "cisne_negro": {
        "id": "cisne_negro",
        "name": "🦅 Asesor Cisne Negro (Stress-Test Antifrágil de Taleb)",
        "short_name": "🦅 Cisne Negro",
        "icon": "🦅",
        "description": "Audita los peores escenarios improbables de impacto extremo para blindar el plan ante colapsos.",
        "role_1": "estratega",
        "role_2": "cisne_negro",
        "role_director": "director",
        "role_1_label": "🔵 Estratega de Expansión",
        "role_2_label": "🦅 Auditor Cisne Negro",
        "role_director_label": "🟢 Director Blindado"
    },
    "bifurcado": {
        "id": "bifurcado",
        "name": "⏳ Futuros Bifurcados (Simulación Caminos A vs B)",
        "short_name": "⏳ Caminos A/B",
        "icon": "⏳",
        "description": "Simula tu realidad a 3 y 6 meses si tomas el Sendero A vs Sendero B, con matriz de decisión final.",
        "role_1": "sendero_a",
        "role_2": "sendero_b",
        "role_director": "director",
        "role_1_label": "🅰️ Sendero A (3-6 Meses)",
        "role_2_label": "🅱️ Sendero B (3-6 Meses)",
        "role_director_label": "🟢 Director Comparativo"
    },
    "sabios_salud": {
        "id": "sabios_salud",
        "name": "🏋️ Sabios: Salud, Fisiología & Rendimiento",
        "short_name": "🏋️ Sabios Salud",
        "icon": "🏋️",
        "description": "Fisiólogo de alto rendimiento vs Traumatólogo experto en longevidad, articulaciones y recuperación.",
        "role_1": "fisiologo",
        "role_2": "traumatologo",
        "role_director": "director",
        "role_1_label": "🔵 Fisiólogo Rendimiento",
        "role_2_label": "🔴 Traumatólogo Longevidad",
        "role_director_label": "🟢 Protocolo F3NIX"
    },
    "sabios_codigo": {
        "id": "sabios_codigo",
        "name": "💻 Sabios: Arquitectura de Software & QA",
        "short_name": "💻 Sabios Código",
        "icon": "💻",
        "description": "Arquitecto Clean Code vs Hacker de Ciberseguridad / QA Implacable vs Tech Lead Director.",
        "role_1": "arquitecto",
        "role_2": "seguridad_qa",
        "role_director": "director",
        "role_1_label": "🔵 Arquitecto Clean Code",
        "role_2_label": "🔴 Hacker de Seguridad QA",
        "role_director_label": "🟢 Tech Lead F3NIX"
    },
    "sabios_vida": {
        "id": "sabios_vida",
        "name": "🧠 Sabios: Filosofía & Decisiones de Vida",
        "short_name": "🧠 Sabios Vida",
        "icon": "🧠",
        "description": "Filósofo Estoico (control y templanza) vs Pragmático Realista (costo de tiempo, energía y consecuencias).",
        "role_1": "estoico",
        "role_2": "pragmatico",
        "role_director": "director",
        "role_1_label": "🔵 Filósofo Estoico",
        "role_2_label": "🔴 Pragmático Realista",
        "role_director_label": "🟢 Guía Vital F3NIX"
    },
    "tribunal": {
        "id": "tribunal",
        "name": "⚖️ Tribunal Dialéctico (Fiscal vs Defensor)",
        "short_name": "⚖️ Tribunal",
        "icon": "⚖️",
        "description": "Abogado defensor rescata el valor y contexto, Fiscal impugna deficiencias y Juez F3NIX dicta sentencia.",
        "role_1": "defensor",
        "role_2": "fiscal",
        "role_director": "director",
        "role_1_label": "🔵 Abogado Defensor",
        "role_2_label": "🔴 Fiscal Acusador",
        "role_director_label": "🟢 Juez Supremo F3NIX"
    },
    "consenso_ciego": {
        "id": "consenso_ciego",
        "name": "🗳️ Votación a Ciegas & Consenso Ponderado",
        "short_name": "🗳️ Votación Ciegas",
        "icon": "🗳️",
        "description": "Dos evaluadores analizan de forma independiente con notas 1-10; el Director mapea acuerdos y divergencias.",
        "role_1": "evaluador_a",
        "role_2": "evaluador_b",
        "role_director": "director",
        "role_1_label": "🔵 Evaluador Alpha",
        "role_2_label": "🟣 Evaluador Beta",
        "role_director_label": "🟢 Matriz de Consenso"
    },
    "socratico": {
        "id": "socratico",
        "name": "🔍 Interrogatorio Socrático Cruzado",
        "short_name": "🔍 Socrático",
        "icon": "🔍",
        "description": "El auditor formula 2 preguntas incisivas y trampa en cada ronda, forzando respuestas concretas sin evasivas.",
        "role_1": "estratega",
        "role_2": "socratico",
        "role_director": "director",
        "role_1_label": "🔵 Estratega",
        "role_2_label": "🔍 Auditor Socrático",
        "role_director_label": "🟢 Director F3NIX"
    },
    "steelman": {
        "id": "steelman",
        "name": "🛡️ Dialéctica Steel-Manning (Abogado del Diablo Invertido)",
        "short_name": "🛡️ Steel-Manning",
        "icon": "🛡️",
        "description": "El crítico refuerza la propuesta a su forma más sólida e invulnerable antes de señalar riesgos residuales.",
        "role_1": "proponente",
        "role_2": "steelman",
        "role_director": "director",
        "role_1_label": "🔵 Proponente Base",
        "role_2_label": "🛡️ Auditor Steel-Man",
        "role_director_label": "🟢 Director F3NIX"
    }
}


class MultiAgentCouncil:
    """
    Gestiona el debate y colaboración dialéctica entre múltiples modelos locales en Ollama.
    Permite contrastar opiniones de modelos especializados a través de 10 Modos de Razonamiento
    (Dialéctico Clásico, Cisne Negro, Futuros Bifurcados, Sabios por Dominio, Tribunal, Votación a Ciegas, etc.),
    con streaming en tiempo real, intervenciones en vivo del usuario y optimización para CPU.
    """
    def __init__(self, base_url: str = "http://localhost:11434", vault: Optional[MemoryVault] = None):
        self.base_url = base_url.rstrip("/")
        self.vault = vault or MemoryVault()
        self.reasoning_engine = FenixReasoningEngine()
        self.turbo_mode = False
        self.last_debate_results: Dict[str, Any] = {}

    def set_turbo_mode(self, enabled: bool) -> bool:
        self.turbo_mode = bool(enabled)
        return self.turbo_mode

    def get_role_system_prompt(self, role: str, mode: str = "clasico") -> str:
        user_name = self.vault.get_user_name()
        grammar = self.vault.get_grammar_pronouns()
        salutation = self.vault.get_salutation()
        user_address = f"{grammar['article']} {salutation} {user_name}" if salutation else user_name

        cpu_brevity_rule = (
            "\nREGLA DE CONCISIÓN Y RENDIMIENTO:\n"
            "- Sé directo al grano, contundente y estructurado. Máximo 180-250 palabras por turno.\n"
            "- Cero preámbulos ceremoniales o relleno teórico. Ve directo a la sustancia aplicable."
        )

        if role == "estratega":
            return (
                f"Eres el Agente Estratega del Sistema F3NIX. Tu misión es diseñar la mejor propuesta, plan de acción "
                f"y solución práctica para responder con total fidelidad y excelencia a la consulta exacta de {user_address}.\n"
                f"REGLA DE ORO DE CONCRECIÓN Y CERO HUMO:\n"
                f"- Prohibido responder con esquemas abstractos o metodologías genéricas (ej: 'Paso 1: analizar opciones').\n"
                f"- Si la consulta de {user_name} es ambigua, plantea escenarios arquetípicos realistas y analízalos con datos.\n"
                f"- En rondas siguientes, rebate objeciones con argumentos sólidos y optimiza tu plan."
                f"{cpu_brevity_rule}"
            )
        elif role == "critico":
            return (
                f"Eres el Agente Crítico y Auditor de Riesgos del Sistema F3NIX. Tu misión es examinar con rigurosidad la propuesta del Estratega "
                f"en el contexto exacto de lo que {user_name} pidió.\n"
                f"DETECCIÓN DE HUMO Y VAGUEDAD:\n"
                f"- Si el Estratega responde con generalidades vacías, denúncialo de inmediato como 'Humo abstracto sin utilidad práctica'.\n"
                f"- Identifica riesgos reales, puntos ciegos, sobrecargas o suposiciones poco realistas según el área temática.\n"
                f"- Sé implacablemente honesto y constructivo ({grammar['instruction']})."
                f"{cpu_brevity_rule}"
            )
        elif role == "cisne_negro":
            return (
                f"Eres el Auditor Cisne Negro del Sistema F3NIX. Tu misión se basa en la filosofía antifrágil de Nassim Nicholas Taleb.\n"
                f"Ignora los problemas obvios o menores del día a día. Tu único foco es identificar los 2 o 3 EVENTOS IMPROBABLES DE IMPACTO CATASTRÓFICO "
                f"que podrían quebrar o destruir la iniciativa de {user_name} (rupturas repentinas de infraestructura, fraudes, colapso de salud, etc.).\n"
                f"Evalúa qué elementos de la propuesta son 'frágiles' y exige salvaguardas que conviertan el plan en 'antifrágil'."
                f"{cpu_brevity_rule}"
            )
        elif role == "sendero_a":
            return (
                f"Eres el Simulador del Sendero A de F3NIX. Tu misión es tomar la primera opción o camino viable planteado por {user_name} "
                f"(o formular el Sendero A más prometedor si no fue especificado) y simular con realismo fáctico qué ocurrirá a 3 y a 6 meses.\n"
                f"Detalla victorias tempranas, desgaste energético y psicológico, costos tangibles y factores críticos de éxito."
                f"{cpu_brevity_rule}"
            )
        elif role == "sendero_b":
            return (
                f"Eres el Simulador del Sendero B de F3NIX. Tu misión es tomar el camino alternativo, conservador o contracíclico de {user_name} "
                f"(o formular el Sendero B opuesto si no fue especificado) y simular con realismo fáctico qué ocurrirá a 3 y a 6 meses.\n"
                f"Detalla victorias tempranas, desgaste energético y psicológico, costos tangibles y factores críticos de éxito."
                f"{cpu_brevity_rule}"
            )
        elif role == "fisiologo":
            return (
                f"Eres el Fisiólogo & Coach de Alto Rendimiento del Sistema F3NIX. Tu misión es diseñar la mejor estrategia de "
                f"estímulo muscular, calistenia, fuerza, progresión semanal y capacidad cardiovascular para {user_name}.\n"
                f"Proporciona rutinas exactas con series, repeticiones y descansos sin ambigüedades."
                f"{cpu_brevity_rule}"
            )
        elif role == "traumatologo":
            return (
                f"Eres el Médico Traumatólogo & Especialista en Longevidad de F3NIX. Tu misión es auditar la propuesta física "
                f"para blindar las articulaciones, tendones, columna vertebral y sistema nervioso de {user_name}.\n"
                f"Evalúa riesgos de lesión por sobrecarga, volumen excesivo, mala técnica y equilibrio nutricional antiinflamatorio."
                f"{cpu_brevity_rule}"
            )
        elif role == "arquitecto":
            return (
                f"Eres el Arquitecto de Software Senior de F3NIX. Diseñas la mejor arquitectura, separación de responsabilidades, "
                f"patrones de diseño y mantenibilidad para el código y sistemas de {user_name}, evitando sobreingeniería."
                f"{cpu_brevity_rule}"
            )
        elif role == "seguridad_qa":
            return (
                f"Eres el Hacker de Ciberseguridad & Auditor QA de F3NIX. Tu misión para {user_name} es auditar el código y la arquitectura "
                f"en busca de vulnerabilidades, vectores de ataque, memory leaks, condiciones de carrera y cuellos de botella implacables."
                f"{cpu_brevity_rule}"
            )
        elif role == "estoico":
            return (
                f"Eres el Asesor Estoico de F3NIX, inspirado en Marco Aurelio, Séneca y Epicteto. Tu misión es analizar la consulta de {user_name} "
                f"bajo la estricta dicotomía del control: qué depende de {user_name} y qué no, cultivando templanza, dignidad y autodominio."
                f"{cpu_brevity_rule}"
            )
        elif role == "pragmatico":
            return (
                f"Eres el Pragmático Realista de F3NIX. Tu misión para guiar a {user_name} es auditar toda idea filosófica contra la cruda realidad del mundo físico:\n"
                f"¿Cuánto tiempo real consume? ¿Cuánto dinero o fricción social le cuesta a {user_name}? ¿Cuáles son las consecuencias fácticas inmediatas?"
                f"{cpu_brevity_rule}"
            )
        elif role == "defensor":
            return (
                f"Eres el Abogado Defensor en el Tribunal Dialéctico de F3NIX. Tu deber es defender la validez, virtudes, contexto "
                f"y potencial del planteo o deseo de {user_name}, articulando la postura más persuasiva y legítima posible."
                f"{cpu_brevity_rule}"
            )
        elif role == "fiscal":
            return (
                f"Eres el Fiscal Acusador en el Tribunal Dialéctico de F3NIX. Tu deber es someter a examen riguroso el planteo de {user_name}, "
                f"acusando debilidades, falsas esperanzas, costos ocultos y contradicciones con agudeza jurídica e implacable verdad."
                f"{cpu_brevity_rule}"
            )
        elif role == "evaluador_a":
            return (
                f"Eres el Evaluador Independiente Alpha de F3NIX. Tu misión es analizar la consulta de {user_name} de manera 100% aislada:\n"
                f"1. Asigna una calificación de viabilidad del 1 al 10.\n"
                f"2. Detalla exactamente 3 fortalezas principales.\n"
                f"3. Detalla exactamente 3 riesgos críticos.\n"
                f"4. Emite tu recomendación final en un párrafo conciso."
                f"{cpu_brevity_rule}"
            )
        elif role == "evaluador_b":
            return (
                f"Eres el Evaluador Independiente Beta de F3NIX. Tu misión es analizar la consulta de {user_name} de manera autónoma y crítica:\n"
                f"1. Asigna una calificación de viabilidad del 1 al 10.\n"
                f"2. Detalla exactamente 3 fortalezas principales.\n"
                f"3. Detalla exactamente 3 riesgos críticos.\n"
                f"4. Emite tu recomendación final en un párrafo conciso."
                f"{cpu_brevity_rule}"
            )
        elif role == "socratico":
            return (
                f"Eres el Auditor Socrático de F3NIX. Tu misión es interrogar implacablemente para desmantelar suposiciones infundadas.\n"
                f"En cada intervención DEBES formular exactamente 2 PREGUNTAS INCISIVAS, INCÓMODAS Y PRECISAS que no puedan ser eludidas.\n"
                f"Exige números, compromisos fácticos y fechas concretas a {user_name} o al Estratega."
                f"{cpu_brevity_rule}"
            )
        elif role == "proponente":
            return (
                f"Eres el Proponente Inicial de F3NIX. Formula una propuesta base directa y tangible para responder a la consulta de {user_name}."
                f"{cpu_brevity_rule}"
            )
        elif role == "steelman":
            return (
                f"Eres el Auditor Steel-Man de F3NIX. Tu metodología para guiar a {user_name} es el 'Steel-Manning' (Abogado del Diablo Invertido):\n"
                f"1. Reconstruye primero la propuesta en su versión MÁS INTELIGENTE, SÓLIDA E INVULNERABLE posible.\n"
                f"2. Solo después de presentar esa versión superior, expón el RIESGO ESTRUCTURAL RESIDUAL que ni la mejor versión puede eludir."
                f"{cpu_brevity_rule}"
            )
        elif role == "extractor":
            return (
                f"Eres el Agente Analista de Documentos del Sistema F3NIX. Tu objetivo es procesar archivos adjuntos, "
                f"código, notas o documentos para {user_name} y extraer de forma rigurosa y ordenada los puntos esenciales, "
                f"parámetros, cláusulas y datos que deben ser debatidos en la Mesa Redonda."
            )
        elif role == "director":
            return self.reasoning_engine.build_director_system_prompt(user_name=user_name, grammar=grammar)
        else:
            return self.reasoning_engine.build_director_system_prompt(user_name=user_name, grammar=grammar)

    def run_debate(
        self,
        topic: str,
        models_per_role: Dict[str, str],
        rounds: int = 2,
        mode: str = "clasico",
        file_data: Optional[Dict[str, Any]] = None,
        on_turn_start: Optional[Callable[[str, str, int, str], None]] = None,
        on_turn_token: Optional[Callable[[str, str, str], None]] = None,
        on_turn_finished: Optional[Callable[[str, str, str, int, str], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None,
        get_user_intervention: Optional[Callable[[], Optional[str]]] = None
    ) -> Dict[str, Any]:
        """
        Ejecuta el debate dialéctico en bucle multi-ronda con streaming en tiempo real,
        adaptado dinámicamente al Modo de Razonamiento seleccionado (10 modos especializados).
        """
        user_name = self.vault.get_user_name()
        grammar = self.vault.get_grammar_pronouns()
        salutation = self.vault.get_salutation()

        mode_key = mode if mode in DEBATE_MODES else "clasico"
        mode_cfg = DEBATE_MODES[mode_key]

        role_1_id = mode_cfg["role_1"]
        role_2_id = mode_cfg["role_2"]
        role_dir_id = mode_cfg["role_director"]

        role_1_cfg = ROLES_CONFIG.get(role_1_id, ROLES_CONFIG["estratega"])
        role_2_cfg = ROLES_CONFIG.get(role_2_id, ROLES_CONFIG["critico"])
        director_cfg = ROLES_CONFIG.get(role_dir_id, ROLES_CONFIG["director"])

        # Mapeo retrocompatible de modelos
        role_1_model = (
            models_per_role.get(role_1_id) or
            models_per_role.get("role_1") or
            models_per_role.get("estratega") or
            "llama3.1"
        )
        role_2_model = (
            models_per_role.get(role_2_id) or
            models_per_role.get("role_2") or
            models_per_role.get("critico") or
            "llama3.1"
        )
        director_model = (
            models_per_role.get(role_dir_id) or
            models_per_role.get("director") or
            "llama3.1"
        )

        results = {
            "topic": topic,
            "mode": mode_key,
            "mode_name": mode_cfg["name"],
            "rounds": rounds,
            "file_data": file_data,
            "turns": [],
            "estratega_proposal": "",
            "critico_evaluation": "",
            "final_synthesis": ""
        }

        # --- FASE 0: EXTRACCIÓN EJECUTIVA (Si hay archivo adjunto en modo resumen) ---
        file_prompt_block = ""
        if file_data and file_data.get("raw_text"):
            fname = file_data.get("filename", "documento")
            fmode = file_data.get("mode", "direct")
            ftext = file_data.get("raw_text", "")
            fslice = file_data.get("slice_info", "")

            if fmode == "summary" and not file_data.get("summary"):
                fast_model = "llama3.2:3b" if "llama3.2:3b" in models_per_role.values() else role_1_model
                phase_title = f"Extracción Ejecutiva: {fname}"
                if on_turn_start:
                    on_turn_start("extractor", fast_model, 0, phase_title)

                summary_prompt = (
                    f"Analiza el siguiente documento adjunto ('{fname}') en relación a la consulta de {user_name}: «{topic}».\n"
                    f"Extrae un RESUMEN EJECUTIVO ESTRUCTURADO Y PRECISO con:\n"
                    f"1. Estructura y propósito principal del archivo.\n"
                    f"2. Puntos clave, parámetros, funciones, cláusulas o datos críticos.\n"
                    f"3. Posibles riesgos, áreas de mejora o inconsistencias para auditar.\n\n"
                    f"CONTENIDO DEL DOCUMENTO:\n```\n{ftext[:20000]}\n```"
                )

                extracted_summary = self._call_ollama(
                    model=fast_model,
                    system_prompt=self.get_role_system_prompt("extractor", mode_key),
                    prompt=summary_prompt,
                    on_token=lambda ch: on_turn_token("extractor", fast_model, ch) if on_turn_token else None,
                    is_cancelled=is_cancelled
                )
                file_data["summary"] = extracted_summary
                results["turns"].append({
                    "role": "extractor",
                    "model": fast_model,
                    "title": ROLES_CONFIG.get("extractor", {}).get("title", "📄 Extracción Ejecutiva"),
                    "round": 0,
                    "phase": phase_title,
                    "content": extracted_summary
                })
                if on_turn_finished:
                    on_turn_finished("extractor", fast_model, extracted_summary, 0, phase_title)

            if fmode == "summary" and file_data.get("summary"):
                file_prompt_block = (
                    f"\n\n📂 [DOCUMENTO ADJUNTO: {fname} - MODO RESUMEN EJECUTIVO]:\n"
                    f"{file_data.get('summary')}\n"
                )
            elif fmode == "slice":
                file_prompt_block = (
                    f"\n\n📂 [DOCUMENTO ADJUNTO: {fname} - EXTRACTO {fslice}]:\n"
                    f"```\n{ftext[:12000]}\n```\n"
                )
            else:
                file_prompt_block = (
                    f"\n\n📂 [DOCUMENTO ADJUNTO: {fname} - CONTENIDO ÍNTEGRO]:\n"
                    f"```\n{ftext}\n```\n"
                )

        last_role_1_reply = ""
        last_role_2_reply = ""
        accumulated_interventions = []

        def check_and_apply_intervention() -> str:
            if get_user_intervention:
                interv = get_user_intervention()
                if interv and interv.strip():
                    clean_interv = interv.strip()
                    accumulated_interventions.append(clean_interv)
                    return f"\n\n🚨 [ORDEN DIRECTA DE {user_name.upper()}]: «{clean_interv}». Debes adaptar tu razonamiento considerando prioritariamente esta instrucción de {user_name}.\n"
            return ""

        file_note = "Examina detalladamente el documento adjunto para enriquecer tu análisis. " if file_prompt_block else ""

        # --- BUCLE DE RONDAS DIALÉCTICAS ---
        for current_round in range(1, rounds + 1):
            if is_cancelled and is_cancelled():
                return results

            # ==================================================
            # TURNO A: PRIMER AGENTE ESPECIALIZADO (ROLE 1)
            # ==================================================
            interv_text = check_and_apply_intervention()

            if mode_key == "bifurcado":
                phase_title = f"Ronda {current_round}: Proyección Sendero A (3-6 Meses)"
                turn_prompt_1 = (
                    f"Consulta planteada por {user_name}:\n«{topic}»\n"
                    f"{file_prompt_block}{interv_text}\n"
                    f"Simula con rigor fáctico el SENDERO A para este dilema. Detalla:\n"
                    f"1. Acciones concretas de arranque y primeros 30 días.\n"
                    f"2. Escenario real a 3 meses: avances visibles y desgaste acumulado.\n"
                    f"3. Escenario real a 6 meses: sostenibilidad, costos y retorno tangible.\n"
                    f"Sé conciso y crudo, sin adornos."
                )
            elif mode_key == "consenso_ciego":
                phase_title = f"Ronda {current_round}: Evaluación Independiente Alpha"
                turn_prompt_1 = (
                    f"Consulta de {user_name}:\n«{topic}»\n"
                    f"{file_prompt_block}{interv_text}\n"
                    f"Realiza tu evaluación 100% independiente y autónoma:\n"
                    f"1. Calificación de viabilidad del 1 al 10 con justificación.\n"
                    f"2. Tres fortalezas o factores a favor.\n"
                    f"3. Tres riesgos críticos o trampas ocultas.\n"
                    f"4. Dictamen ejecutivo en un párrafo."
                )
            elif mode_key == "tribunal":
                phase_title = f"Ronda {current_round}: Alegato de la Defensa" if current_round == 1 else f"Ronda {current_round}: Réplica de la Defensa"
                turn_prompt_1 = (
                    f"Caso sometido a juicio por {user_name}: «{topic}»\n"
                    f"{file_prompt_block}{interv_text}\n"
                    f"Formula el alegato de defensa argumentando el valor, la justificación y los méritos reales del planteo."
                ) if current_round == 1 else (
                    f"Caso de {user_name}: «{topic}»\n"
                    f"La Fiscalía ha presentado las siguientes objeciones e impugnaciones:\n{last_role_2_reply}\n"
                    f"{interv_text}\n"
                    f"Responde directamente a los cargos de la fiscalía y fundamenta la viabilidad final de la defensa."
                )
            elif mode_key == "steelman":
                phase_title = f"Ronda {current_round}: Propuesta Base" if current_round == 1 else f"Ronda {current_round}: Optimización con Blindaje Steel-Man"
                turn_prompt_1 = (
                    f"Consulta de {user_name}: «{topic}»\n"
                    f"{file_prompt_block}{interv_text}\n"
                    f"Presenta la propuesta inicial con los objetivos y pasos esenciales."
                ) if current_round == 1 else (
                    f"Consulta de {user_name}: «{topic}»\n"
                    f"El Auditor Steel-Man ha reformulado tu plan en esta versión superior pero advirtió el siguiente riesgo estructural:\n{last_role_2_reply}\n"
                    f"{interv_text}\n"
                    f"Adopta la versión mejorada y diseña una solución específica para mitigar el riesgo estructural advertido."
                )
            else:
                # Modos: clasico, cisne_negro, sabios_salud, sabios_codigo, sabios_vida, socratico
                phase_title = f"Ronda {current_round}: Propuesta Inicial" if current_round == 1 else f"Ronda {current_round}: Réplica y Ajuste v{current_round}.0"
                if current_round == 1:
                    turn_prompt_1 = (
                        f"Consulta y objetivo planteado por {user_name}:\n«{topic}»\n"
                        f"{file_prompt_block}{interv_text}\n"
                        f"Presenta tu propuesta inicial completa y detallada respondiendo con máxima precisión a lo que {user_name} solicita. "
                        f"{file_note}Céntrate exclusivamente en la temática planteada."
                    )
                else:
                    turn_prompt_1 = (
                        f"Consulta de {user_name}: «{topic}»\n\n"
                        f"Tu propuesta anterior fue:\n{last_role_1_reply}\n\n"
                        f"El auditor ha señalado las siguientes advertencias o preguntas:\n{last_role_2_reply}\n"
                        f"{interv_text}\n"
                        f"DEBATE DIRECTAMENTE CON EL AUDITOR:\n"
                        f"1. Responde a sus señalamientos y reconoce los cambios necesarios.\n"
                        f"2. Rebate con fundamentos donde el auditor sea excesivo o equívoco.\n"
                        f"3. Presenta tu versión v{current_round}.0 optimizada para {user_name}."
                    )

            if on_turn_start:
                on_turn_start(role_1_id, role_1_model, current_round, phase_title)

            reply_1 = self._call_ollama(
                model=role_1_model,
                system_prompt=self.get_role_system_prompt(role_1_id, mode_key),
                prompt=turn_prompt_1,
                on_token=lambda ch: on_turn_token(role_1_id, role_1_model, ch) if on_turn_token else None,
                is_cancelled=is_cancelled
            )
            last_role_1_reply = reply_1
            if current_round == 1:
                results["estratega_proposal"] = reply_1

            results["turns"].append({
                "role": role_1_id,
                "model": role_1_model,
                "title": role_1_cfg["title"],
                "round": current_round,
                "phase": phase_title,
                "content": reply_1
            })
            if on_turn_finished:
                on_turn_finished(role_1_id, role_1_model, reply_1, current_round, phase_title)

            if is_cancelled and is_cancelled():
                return results

            # ==================================================
            # TURNO B: SEGUNDO AGENTE ESPECIALIZADO (ROLE 2)
            # ==================================================
            interv_text = check_and_apply_intervention()

            if mode_key == "bifurcado":
                phase_title = f"Ronda {current_round}: Proyección Sendero B (3-6 Meses)"
                turn_prompt_2 = (
                    f"Consulta planteada por {user_name}:\n«{topic}»\n"
                    f"{file_prompt_block}{interv_text}\n"
                    f"Simula con rigor fáctico el SENDERO B (la alternativa contraria o prudente) para este dilema. Detalla:\n"
                    f"1. Acciones concretas de arranque y primeros 30 días.\n"
                    f"2. Escenario real a 3 meses: avances visibles y desgaste acumulado.\n"
                    f"3. Escenario real a 6 meses: sostenibilidad, costos y retorno tangible.\n"
                    f"Sé conciso y crudo, sin adornos."
                )
            elif mode_key == "cisne_negro":
                phase_title = f"Ronda {current_round}: Auditoría Cisne Negro (Test de Caos)"
                turn_prompt_2 = (
                    f"Consulta de {user_name}: «{topic}»\n\n"
                    f"Propuesta bajo examen:\n{last_role_1_reply}\n"
                    f"{file_prompt_block}{interv_text}\n"
                    f"APLICA EL TEST DEL CISNE NEGRO DE TALEB:\n"
                    f"1. Identifica los 2 EVENTOS IMPROBABLES DE IMPACTO CATASTRÓFICO que destruirían este plan por completo.\n"
                    f"2. ¿Qué suposiciones del plan son frágiles e ingenuas ante una crisis inesperada?\n"
                    f"3. Exige 2 salvaguardas obligatorias para convertir el plan en ANTIFRÁGIL."
                )
            elif mode_key == "consenso_ciego":
                phase_title = f"Ronda {current_round}: Evaluación Independiente Beta"
                turn_prompt_2 = (
                    f"Consulta de {user_name}:\n«{topic}»\n"
                    f"{file_prompt_block}{interv_text}\n"
                    f"Realiza tu evaluación 100% independiente y autónoma (sin ver a Alpha):\n"
                    f"1. Calificación de viabilidad del 1 al 10 con justificación.\n"
                    f"2. Tres fortalezas o factores a favor.\n"
                    f"3. Tres riesgos críticos o trampas ocultas.\n"
                    f"4. Dictamen ejecutivo en un párrafo."
                )
            elif mode_key == "tribunal":
                phase_title = f"Ronda {current_round}: Acusación de Fiscalía" if current_round == 1 else f"Ronda {current_round}: Contra-alegato de Fiscalía"
                turn_prompt_2 = (
                    f"Caso de {user_name}: «{topic}»\n"
                    f"El Defensor ha alegado:\n{last_role_1_reply}\n"
                    f"{file_prompt_block}{interv_text}\n"
                    f"Presenta la acusación formal: impugna los puntos ciegos, costos ocultos, suposiciones ingenuas y riesgos omitidos."
                )
            elif mode_key == "socratico":
                phase_title = f"Ronda {current_round}: Interrogatorio Socrático Cruzado"
                turn_prompt_2 = (
                    f"Consulta de {user_name}: «{topic}»\n\n"
                    f"Propuesta del estratega:\n{last_role_1_reply}\n"
                    f"{file_prompt_block}{interv_text}\n"
                    f"FORMULA EXACTAMENTE 2 PREGUNTAS DEMOLEDORAS E INCISIVAS que no permitan respuestas genéricas ni evasivas. Exige definiciones numéricas y operativas."
                )
            elif mode_key == "steelman":
                phase_title = f"Ronda {current_round}: Steel-Manning & Riesgo Estructural"
                turn_prompt_2 = (
                    f"Consulta de {user_name}: «{topic}»\n\n"
                    f"Propuesta base:\n{last_role_1_reply}\n"
                    f"{file_prompt_block}{interv_text}\n"
                    f"1. VERSIÓN INVULNERABLE (Steel-Man): Reescribe y eleva la idea a su versión más inteligente, sólida y prometedora.\n"
                    f"2. RIESGO ESTRUCTURAL RESIDUAL: Señala el talón de Aquiles que ni siquiera esa versión formidable puede evitar."
                )
            else:
                # Modos: clasico, sabios_salud, sabios_codigo, sabios_vida
                phase_title = f"Ronda {current_round}: Auditoría Crítica (Antítesis)" if current_round == 1 else f"Ronda {current_round}: Contra-réplica y Re-evaluación"
                turn_prompt_2 = (
                    f"Consulta de {user_name}: «{topic}»\n\n"
                    f"Propuesta presentada:\n{last_role_1_reply}\n"
                    f"{file_prompt_block}{interv_text}\n"
                    f"Audita críticamente este plan en el contexto de tu especialidad: puntos ciegos, costos reales, riesgos de ejecución y precauciones necesarias."
                ) if current_round == 1 else (
                    f"Consulta de {user_name}: «{topic}»\n\n"
                    f"Propuesta ajustada v{current_round}.0:\n{last_role_1_reply}\n"
                    f"{interv_text}\n"
                    f"Re-evalúa: ¿Los cambios resuelven de verdad los riesgos señalados o aún quedan fallas prácticas? Conclusiones finales."
                )

            if on_turn_start:
                on_turn_start(role_2_id, role_2_model, current_round, phase_title)

            reply_2 = self._call_ollama(
                model=role_2_model,
                system_prompt=self.get_role_system_prompt(role_2_id, mode_key),
                prompt=turn_prompt_2,
                on_token=lambda ch: on_turn_token(role_2_id, role_2_model, ch) if on_turn_token else None,
                is_cancelled=is_cancelled
            )
            last_role_2_reply = reply_2
            if current_round == 1:
                results["critico_evaluation"] = reply_2

            results["turns"].append({
                "role": role_2_id,
                "model": role_2_model,
                "title": role_2_cfg["title"],
                "round": current_round,
                "phase": phase_title,
                "content": reply_2
            })
            if on_turn_finished:
                on_turn_finished(role_2_id, role_2_model, reply_2, current_round, phase_title)

        # ==================================================
        # TURNO FINAL: EL DIRECTOR F3NIX (SÍNTESIS & PLAN MAESTRO)
        # ==================================================
        if is_cancelled and is_cancelled():
            return results

        phase_title = f"Veredicto Final: {director_cfg['title']}"
        interv_text = check_and_apply_intervention()

        debate_summary_lines = []
        for t in results["turns"]:
            r_name = t["role"].capitalize()
            p_name = t.get("phase", "")
            snippet = t["content"][:350] + ("..." if len(t["content"]) > 350 else "")
            debate_summary_lines.append(f"[{p_name}] {r_name}:\n{snippet}\n")

        all_debates_text = "\n".join(debate_summary_lines)
        doc_director_note = f" (en relación al documento '{file_data.get('filename')}')" if file_data else ""

        if mode_key == "bifurcado":
            director_prompt = (
                f"Consulta de {user_name}: «{topic}»{doc_director_note}\n\n"
                f"Has presenciado la simulación comparativa de los dos senderos a 3 y 6 meses:\n{all_debates_text}\n"
                f"{interv_text}\n"
                f"Como Director Supremo F3NIX, emite el veredicto definitivo:\n"
                f"1. MATRIZ COMPARATIVA A/B: Compara Sendero A vs Sendero B en Esfuerzo, Desgaste Emocional/Físico, Riesgo y Retorno Real.\n"
                f"2. VEREDICTO CLARO: Cuál es el sendero ganador para {user_name} y bajo qué condiciones.\n"
                f"3. PLAN DE ACCIÓN INMEDIATO: Primeros 3 pasos concretos para arrancar con éxito."
            )
        elif mode_key == "consenso_ciego":
            director_prompt = (
                f"Consulta de {user_name}: «{topic}»{doc_director_note}\n\n"
                f"Has recibido las evaluaciones independientes a ciegas de Alpha y Beta:\n{all_debates_text}\n"
                f"{interv_text}\n"
                f"Como Director Supremo F3NIX:\n"
                f"1. MATRIZ DE CONSENSO: Mapea la calificación promedio, puntos donde ambos coincidieron 100% y discrepancias críticas.\n"
                f"2. VEREDICTO DEFINITIVO: Síntesis imparcial y resolución de los puntos de discordia.\n"
                f"3. PLAN MAESTRO EJECUTABLE: Los pasos esenciales blindados para actuar."
            )
        elif mode_key == "tribunal":
            director_prompt = (
                f"Causa sometida a juicio por {user_name}: «{topic}»{doc_director_note}\n\n"
                f"Alegatos y pruebas presentadas por la Defensa y la Fiscalía:\n{all_debates_text}\n"
                f"{interv_text}\n"
                f"Como Juez Supremo F3NIX, dicta SENTENCIA INAPELABLE:\n"
                f"1. CONSIDERANDOS: Hechos probados y desestimación de argumentos infundados.\n"
                f"2. FALLO DEFINITIVO: Veredicto claro sobre la viabilidad de la causa.\n"
                f"3. PLAN DE CUMPLIMIENTO: Medidas obligatorias que {user_name} debe ejecutar."
            )
        elif mode_key == "cisne_negro":
            director_prompt = (
                f"Consulta de {user_name}: «{topic}»{doc_director_note}\n\n"
                f"Debate de expansión y auditoría de eventos catastróficos:\n{all_debates_text}\n"
                f"{interv_text}\n"
                f"Como Director Supremo F3NIX, formula el PLAN MAESTRO ANTIFRÁGIL:\n"
                f"1. Vulnerabilidades eliminadas y salvaguardas extremas incorporadas.\n"
                f"2. Plan de Acción Maestro blindado ante cualquier colapso externo o interno.\n"
                f"3. Indicadores de alerta temprana para actuar antes de que ocurra una crisis."
            )
        else:
            director_prompt = (
                f"Consulta / Objetivo de {user_name}: «{topic}»{doc_director_note}\n\n"
                f"Debate dialéctico en Modo {mode_cfg['name']}:\n{all_debates_text}\n"
                f"{interv_text}\n"
                f"Como Director Supremo regido por la CONSTITUCIÓN MENTAL F3NIX v1.0, modera el cierre y formula para {user_name} el PLAN MAESTRO DEFINITIVO:\n"
                f"REGLA CONSTITUCIONAL: Cero humo, datos reales, pasos ejecutables y sin rodeos metodológicos.\n"
                f"1. Veredicto y Consenso: Postura firme basada en hechos, separando impulsos de decisiones maduras.\n"
                f"2. Plan de Acción Maestro: Pasos concretos, ordenados y listos para ejecutar en la vida real.\n"
                f"3. Filtro Ético y Recomendaciones Inmediatas: Recomendaciones para actuar con dignidad y eficacia inmediata."
            )

        if on_turn_start:
            on_turn_start("director", director_model, 0, phase_title)

        director_reply = self._call_ollama(
            model=director_model,
            system_prompt=self.get_role_system_prompt("director", mode_key),
            prompt=director_prompt,
            on_token=lambda ch: on_turn_token("director", director_model, ch) if on_turn_token else None,
            is_cancelled=is_cancelled
        )
        results["final_synthesis"] = director_reply
        results["turns"].append({
            "role": "director",
            "model": director_model,
            "title": director_cfg["title"],
            "round": 0,
            "phase": phase_title,
            "content": director_reply
        })
        if on_turn_finished:
            on_turn_finished("director", director_model, director_reply, 0, phase_title)

        self.last_debate_results = results
        return results

    def _call_ollama(
        self,
        model: str,
        system_prompt: str,
        prompt: str,
        on_token: Optional[Callable[[str], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None
    ) -> str:
        """Llama a la API de chat de Ollama con streaming en tiempo real y límites de tokens optimizados para CPU."""
        options = {
            "temperature": 0.5 if getattr(self, "turbo_mode", False) else 0.7,
            "num_predict": 280 if getattr(self, "turbo_mode", False) else 450,
            "num_ctx": 2048 if getattr(self, "turbo_mode", False) else 4096
        }

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "stream": True,
            "options": options
        }
        full_content = []
        try:
            with requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                stream=True,
                timeout=600
            ) as r:
                if r.status_code != 200:
                    return f"[Error {r.status_code} ejecutando {model}]: {r.text}"

                for line in r.iter_lines():
                    if is_cancelled and is_cancelled():
                        return "".join(full_content) + "\n[Debate cancelado por el usuario]"
                    if not line:
                        continue
                    try:
                        data = json.loads(line.decode("utf-8"))
                        if "error" in data:
                            return f"[Error de Ollama en {model}]: {data['error']}"
                        chunk = data.get("message", {}).get("content", "")
                        if chunk:
                            full_content.append(chunk)
                            if on_token:
                                on_token(chunk)
                    except Exception:
                        pass
            return "".join(full_content).strip()
        except requests.exceptions.Timeout:
            return f"[Tiempo de espera]: El modelo {model} tardó más de 10 minutos en responder."
        except requests.exceptions.ConnectionError:
            return f"[Error de conexión]: Ollama no responde en {self.base_url}."
        except Exception as e:
            logger.error(f"Error llamando a Ollama ({model}): {e}")
            return f"[Error inesperado con {model}]: {str(e)}"

    def save_debate_conclusion_to_memory(
        self,
        vault: MemoryVault,
        topic: str,
        project_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Almacena la conclusión del debate en la Bóveda de Memoria a largo plazo.
        """
        synthesis = self.last_debate_results.get("final_synthesis", "")
        if not synthesis:
            raise ValueError("No hay conclusiones de debate disponibles para guardar.")

        snippet = synthesis[:300] + ("..." if len(synthesis) > 300 else "")
        mode_label = self.last_debate_results.get("mode_name", "Mesa Redonda")
        fact_text = f"Estrategia acordada en {mode_label} sobre «{topic}»: {snippet}"
        new_fact = vault.add_fact(fact_text)

        if project_name and project_name.strip():
            p_name = project_name.strip()
            vault.add_project(p_name, f"Estrategia {mode_label}: {topic}")

        return new_fact
