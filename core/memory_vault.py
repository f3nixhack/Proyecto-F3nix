import os
import json
import time
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

MEMORY_FILE_PATH = "f3nix_memory.json"

DEFAULT_MEMORY = {
    "user_name": "Fenix",
    "user_gender": "Hombre",
    "salutation": "Comandante",
    "role": "Desarrollador de Software y Creador del Proyecto F3nix",
    "tone_preference": "Directo, técnico, resolutivo y amigable",
    "coding_guidelines": [
      "Código limpio, modular y bien estructurado",
      "Uso de tipado y buenas prácticas",
      "Priorizar eficiencia y arquitectura asíncrona"
    ],
    "custom_debate_presets": [],
    "active_projects": {
      "Proyecto F3nix": "Asistente de escritorio de IA local para Windows 11 con HUD flotante, voz TTS/STT y herramientas."
    },
    "facts": [
      {"id": 1, "text": "El usuario principal y comandante del sistema es Fenix.", "date": "2026-09-15"},
      {"id": 2, "text": "Entorno de ejecución: Windows 11 con Ollama para inferencia 100% local y privada.", "date": "2026-09-15"}
    ]
}

class MemoryVault:
    """
    Bóveda de memoria persistente a largo plazo estilo Hermes Desktop.
    Guarda recuerdos sobre el usuario, proyectos y preferencias en disco.
    """
    def __init__(self, filepath: str = MEMORY_FILE_PATH):
        self.filepath = filepath
        self.data = self._load()

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error cargando {self.filepath}: {e}")
        # Si no existe, guardar defaults
        self._save(DEFAULT_MEMORY)
        return dict(DEFAULT_MEMORY)

    def _save(self, data: Optional[Dict[str, Any]] = None):
        if data is None:
            data = self.data
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error guardando {self.filepath}: {e}")

    def add_fact(self, text: str) -> Dict[str, Any]:
        """Añade un nuevo recuerdo a la memoria a largo plazo."""
        facts = self.data.get("facts", [])
        new_id = max([f.get("id", 0) for f in facts], default=0) + 1
        date_str = time.strftime("%Y-%m-%d %H:%M")
        new_item = {"id": new_id, "text": text.strip(), "date": date_str}
        facts.append(new_item)
        self.data["facts"] = facts
        self._save()
        logger.info(f"Nuevo recuerdo grabado en F3nix: {text}")
        return new_item

    def auto_extract_facts(self, prompt: str) -> Optional[str]:
        """
        Detector pasivo en segundo plano: extrae automáticamente hechos, preferencias
        y proyectos mencionados naturalmente en la conversación sin requerir 'recuerda que'.
        """
        clean = prompt.strip()
        # Ignorar preguntas, comandos cortos o dictados
        if not clean or clean.startswith("¿") or clean.endswith("?") or len(clean) < 12:
            return None
        lower = clean.lower()
        if any(lower.startswith(w) for w in ["escribe:", "busca ", "abre ", "cierra ", "cuál ", "qué ", "cómo ", "por qué"]):
            return None

        import re
        patterns = [
            (r"(?:mi lenguaje favorito es|suelo programar en|programo principalmente en|mi stack es|desarrollo con)\s+([^.,;]+)", "Tecnología preferida: {}"),
            (r"(?:estoy aprendiendo|estoy estudiando)\s+([^.,;]+)", "En aprendizaje actual: {}"),
            (r"(?:mi nuevo proyecto es|mi proyecto se llama|estoy creando una app de|estoy construyendo)\s+([^.,;]+)", "Proyecto en desarrollo: {}"),
            (r"(?:trabajo como|mi trabajo es|mi profesión es|me dedico a)\s+([^.,;]+)", "Profesión/Rol: {}"),
            (r"(?:vivo en|soy de|radico en)\s+([^.,;]+)", "Ubicación: {}"),
            (r"(?:mi cumpleaños es el|cumplo años el)\s+([^.,;]+)", "Cumpleaños: {}"),
            (r"(?:prefiero respuestas|prefiero que respondas|me gusta que seas)\s+([^.,;]+)", "Preferencia de respuesta: {}")
        ]

        for pat, template in patterns:
            m = re.search(pat, lower)
            if m:
                val = clean[m.start(1):m.end(1)].strip(" :.,;")
                if len(val) >= 3 and len(val) <= 60:
                    fact_str = template.format(val)
                    # Comprobar si ya existe un recuerdo sustancialmente idéntico
                    existing = [f.get("text", "").lower() for f in self.data.get("facts", [])]
                    if not any(val.lower() in ex for ex in existing):
                        self.add_fact(fact_str)
                        return fact_str
        return None

    def delete_fact(self, fact_id: int) -> bool:
        """Elimina un recuerdo específico por su ID."""
        facts = self.data.get("facts", [])
        initial_len = len(facts)
        self.data["facts"] = [f for f in facts if f.get("id") != fact_id]
        if len(self.data["facts"]) < initial_len:
            self._save()
            return True
        return False

    def add_project(self, name: str, description: str):
        """Registra un nuevo proyecto en la memoria de F3nix (con descripción concisa)."""
        if "active_projects" not in self.data:
            self.data["active_projects"] = {}
        desc = description.strip()
        if len(desc) > 100:
            desc = desc[:97] + "..."
        self.data["active_projects"][name.strip()] = desc
        self._save()

    def set_user_identity(self, user_name: Optional[str] = None, user_gender: Optional[str] = None, salutation: Optional[str] = None):
        """Actualiza la identidad y preferencias de tratamiento del usuario."""
        if user_name is not None:
            self.data["user_name"] = str(user_name).strip()
        if user_gender is not None:
            self.data["user_gender"] = str(user_gender).strip()
        if salutation is not None:
            self.data["salutation"] = str(salutation).strip()
        self._save()

    def get_user_name(self) -> str:
        name = str(self.data.get("user_name") or "Usuario").strip()
        return name if name else "Usuario"

    def get_user_gender(self) -> str:
        return str(self.data.get("user_gender") or "Hombre")

    def get_salutation(self) -> str:
        sal = str(self.data.get("salutation") or "").strip()
        return sal if sal else self.get_user_name()

    def get_grammar_pronouns(self) -> Dict[str, str]:
        """
        Retorna reglas de concordancia de género gramatical para tratar correctamente al usuario.
        """
        gender = self.get_user_gender().lower()
        if "mujer" in gender or "femenin" in gender:
            return {
                "gender": "Femenino",
                "pronoun": "ella",
                "article": "la",
                "welcome": "bienvenida",
                "ready": "lista",
                "president": "Presidenta",
                "friend": "amiga",
                "commander": "la Comandante",
                "instruction": "Tratar a la usuaria como mujer ('ella', 'estimada', 'bienvenida', 'lista', 'amiga', 'la comandante')."
            }
        elif "neutro" in gender or "no binario" in gender or "prefiero no" in gender:
            return {
                "gender": "Neutro",
                "pronoun": "elle",
                "article": "le",
                "welcome": "bienvenid@",
                "ready": "list@",
                "president": "Presidente/a",
                "friend": "amig@",
                "commander": "Comandante",
                "instruction": "Tratar con lenguaje neutro o inclusivo ('estimad@', 'bienvenid@', 'Comandante')."
            }
        else: # Hombre / Masculino por defecto
            return {
                "gender": "Masculino",
                "pronoun": "él",
                "article": "el",
                "welcome": "bienvenido",
                "ready": "listo",
                "president": "Presidente",
                "friend": "amigo",
                "commander": "el Comandante",
                "instruction": "Tratar al usuario como hombre ('él', 'estimado', 'bienvenido', 'listo', 'amigo', 'el comandante')."
            }

    def get_custom_debate_presets(self) -> List[Dict[str, str]]:
        return self.data.get("custom_debate_presets", [])

    def add_custom_debate_preset(self, title: str, topic: str) -> bool:
        if "custom_debate_presets" not in self.data:
            self.data["custom_debate_presets"] = []
        self.data["custom_debate_presets"] = [p for p in self.data["custom_debate_presets"] if p.get("title") != title]
        self.data["custom_debate_presets"].append({
            "title": title.strip(),
            "topic": topic.strip()
        })
        self._save()
        return True

    def delete_custom_debate_preset(self, title: str) -> bool:
        presets = self.data.get("custom_debate_presets", [])
        new_presets = [p for p in presets if p.get("title") != title]
        if len(new_presets) < len(presets):
            self.data["custom_debate_presets"] = new_presets
            self._save()
            return True
        return False

    def record_life_case(self, situation: str, action: str, motive: str, principle: str) -> Dict[str, Any]:
        """
        Registra un caso empírico de vida según la Constitución F3NIX v1.0.
        """
        cases = self.data.get("life_cases", [])
        new_id = max([c.get("id", 0) for c in cases], default=0) + 1
        new_case = {
            "id": new_id,
            "situation": situation.strip()[:150],
            "action": action.strip()[:150],
            "motive": motive.strip()[:100],
            "principle": principle.strip()[:60],
            "date": time.strftime("%Y-%m-%d %H:%M")
        }
        cases.append(new_case)
        self.data["life_cases"] = cases
        self._save()
        return new_case

    def get_life_cases(self) -> List[Dict[str, Any]]:
        return self.data.get("life_cases", [])

    def delete_life_case(self, case_id: int) -> bool:
        cases = self.data.get("life_cases", [])
        initial_len = len(cases)
        self.data["life_cases"] = [c for c in cases if c.get("id") != case_id]
        if len(self.data["life_cases"]) < initial_len:
            self._save()
            return True
        return False

    def get_memory_context(self) -> str:
        """
        Genera el bloque de contexto de memoria conciso (<600 caracteres)
        para máxima velocidad de inferencia en CPUs de escritorio sin GPU.
        """
        user_name = self.get_user_name()
        grammar = self.get_grammar_pronouns()
        salutation = self.get_salutation()
        role = self.data.get("role", "Usuario")
        tone = self.data.get("tone_preference", "Conciso, resolutivo y amigable")

        # Proyectos más recientes (máx 3, descripción concisa)
        projects = self.data.get("active_projects", {})
        recent_proj_items = list(projects.items())[-3:]
        proj_lines = []
        for k, v in recent_proj_items:
            v_short = (v[:60] + "...") if len(v) > 60 else v
            k_short = (k[:35] + "...") if len(k) > 35 else k
            proj_lines.append(f"  - {k_short}: {v_short}")
        proj_str = "\n".join(proj_lines) if proj_lines else "  - Ninguno activo."

        # Hechos más recientes (máx 3, truncados a 80 caracteres para no saturar tokens)
        facts = self.data.get("facts", [])
        recent_facts = facts[-3:]
        facts_lines = []
        for f in recent_facts:
            txt = f.get("text", "")
            txt_short = (txt[:80] + "...") if len(txt) > 80 else txt
            facts_lines.append(f"  - {txt_short}")
        facts_str = "\n".join(facts_lines) if facts_lines else "  - Sin notas."

        # Casos de vida recientes (máx 2)
        life_cases = self.data.get("life_cases", [])
        recent_cases = life_cases[-2:]
        cases_lines = []
        for c in recent_cases:
            p = c.get("principle", "Principio")[:30]
            sit = c.get("situation", "")[:50]
            cases_lines.append(f"  - [{p}] {sit}")
        cases_str = f"\n• Lecciones aprendidas:\n" + "\n".join(cases_lines) if cases_lines else ""

        return (
            f"[MEMORIA DEL USUARIO (Hermes Vault)]:\n"
            f"• Usuario: {user_name} ({role}) | Título: {salutation}\n"
            f"• Tratamiento: Género {grammar['gender']} ({grammar['instruction']})\n"
            f"• Tono: {tone}\n"
            f"• Proyectos:\n{proj_str}\n"
            f"• Notas del usuario:\n{facts_str}"
            f"{cases_str}"
        )
