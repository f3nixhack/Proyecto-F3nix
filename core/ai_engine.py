import os
import re
import json
import logging
import threading
from typing import List, Dict, Optional, Callable
import requests

from core.f3nix_tools import F3nixTools
from core.memory_vault import MemoryVault
from core.f3nix_rag import LocalRAG
from core.instant_cache import InstantCache
from core.fenix_reasoning import FenixReasoningEngine
from core.task_manager import TaskManager

logger = logging.getLogger(__name__)

class AIEngine:
    """
    Gestiona la conexión con Ollama, memoria conversacional, memoria persistente (Hermes Vault),
    base de conocimiento RAG local, selección de modelos, búsqueda web DuckDuckGo,
    visión de pantalla, temporizadores, razonamiento constitucional y planificación de tareas.
    """
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = "llama3.2:3b",
        memory: Optional[MemoryVault] = None,
        rag: Optional[LocalRAG] = None,
        task_manager: Optional[TaskManager] = None
    ):
        self.base_url = base_url.rstrip("/")
        self.current_model = default_model
        self.memory = memory or MemoryVault()
        self.rag = rag or LocalRAG()
        self.task_manager = task_manager or TaskManager()
        self.reasoning = FenixReasoningEngine()
        self.session_file = "f3nix_session.json"
        self.max_history_turns = 10
        self.history: List[Dict[str, str]] = self._load_session()
        self.active_document: Optional[str] = None
        self.active_document_name: Optional[str] = None
        self.on_timer_finished_callback: Optional[Callable[[str], None]] = None
        self.on_activity_callback: Optional[Callable[[str, str, str], None]] = None
        self.turbo_mode: bool = False
        self._chat_lock = threading.Lock()
        self._ensure_valid_model()
        self.warmup_model()

    def _load_session(self) -> List[Dict[str, str]]:
        """Carga el historial de la última conversación para persistencia de sesión."""
        if os.path.exists(self.session_file):
            try:
                with open(self.session_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        logger.info(f"Sesión anterior recuperada: {len(data)} turnos.")
                        return data[-(self.max_history_turns * 2):]
            except Exception as e:
                logger.error(f"Error cargando sesión anterior: {e}")
        return []

    def _save_session(self):
        """Guarda en disco los últimos turnos de conversación de la sesión actual."""
        try:
            with open(self.session_file, "w", encoding="utf-8") as f:
                json.dump(self.history[-(self.max_history_turns * 2):], f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error guardando sesión de conversación: {e}")

    def warmup_model(self):
        """Pre-carga el modelo principal en RAM con keep_alive para eliminar el retardo de arranque en frío."""
        def _warm():
            try:
                payload = {
                    "model": self.current_model,
                    "keep_alive": "60m"
                }
                requests.post(f"{self.base_url}/api/generate", json=payload, timeout=5)
                logger.info(f"Ollama Warmup completado para {self.current_model} (keep_alive: 60m).")
            except Exception as e:
                logger.debug(f"Ollama Warmup ignorado: {e}")

        threading.Thread(target=_warm, daemon=True).start()

    def set_turbo_mode(self, enabled: bool) -> bool:
        """Activa o desactiva el Modo Turbo para respuestas inmediatas."""
        self.turbo_mode = bool(enabled)
        logger.info(f"AIEngine: Modo Turbo {'activado' if self.turbo_mode else 'desactivado'}")
        self._log_activity("Sistema", f"Modo Turbo {'Activado' if self.turbo_mode else 'Desactivado'}", "Respuestas ultra-rápidas")
        return self.turbo_mode

    def is_server_online(self) -> bool:
        """Verifica si el servidor de Ollama está en ejecución."""
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def list_installed_models(self) -> List[str]:
        """Devuelve la lista de nombres de modelos instalados en Ollama."""
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=2)
            if r.status_code == 200:
                data = r.json()
                return [m.get("name", "") for m in data.get("models", [])]
        except requests.exceptions.ConnectionError:
            logger.warning(f"Ollama no está en ejecución en {self.base_url}.")
        except Exception as e:
            logger.debug(f"Nota listando modelos de Ollama: {e}")
        return []

    def _ensure_valid_model(self):
        """Si el modelo por defecto no existe, busca una alternativa instalada dando prioridad a modelos rápidos."""
        installed = self.list_installed_models()
        if not installed:
            return
        
        names = [m.split(":")[0] for m in installed]
        if self.current_model not in installed and self.current_model not in names:
            fast_priority = ["llama3.2:3b", "llama3.2", "qwen2.5:3b", "hermes3", "llama"]
            for fp in fast_priority:
                for candidate in installed:
                    if fp in candidate.lower():
                        self.current_model = candidate
                        return
            self.current_model = installed[0]

    def set_model(self, model_name: str) -> bool:
        """Cambia el modelo activo dinámicamente."""
        self.current_model = model_name
        logger.info(f"Modelo de IA cambiado a: {model_name}")
        return True

    def select_optimal_model(self, prompt: str, is_turbo: bool = False, has_image: bool = False) -> tuple:
        """
        Smart Router Cerebral: Selecciona automáticamente el modelo óptimo instalado
        según el tipo de consulta para maximizar velocidad y precisión.
        Retorna: (model_name, brain_badge)
        """
        installed = self.list_installed_models()
        if not installed:
            return (self.current_model, "Predeterminado 🤖")

        # 1. Visión Multimodal (si hay imagen adjunta o solicitada)
        if has_image:
            for vm in ["moondream", "llava", "vision", "minicpm", "bakllava"]:
                for m in installed:
                    if vm in m.lower():
                        return (m, "Visión 👁️ (Moondream)")

        # 2. Modo Turbo forzado
        if is_turbo:
            for tb in ["llama3.2:3b", "llama3.2:1b", "qwen2.5:1.5b", "smollm2"]:
                for m in installed:
                    if tb in m.lower():
                        return (m, "Turbo ⚡")

        p_lower = prompt.lower()

        # 3. Modo Abogado del Diablo / Steelman Constitucional
        steelman_triggers = [
            "abogado del diablo", "cuestiona mi idea", "cuestiona este plan", "critica mi plan",
            "critica mi propuesta", "destruye mi propuesta", "destruye este plan", "puntos ciegos",
            "contraargumenta", "steelman", "criterio firme", "evalúa este dilema", "evalua este dilema"
        ]
        if any(w in p_lower for w in steelman_triggers):
            for dp in ["deepseek-r1", "phi4", "llama-3.1-8b", "hermes3"]:
                for m in installed:
                    if dp in m.lower():
                        return (m, "Abogado del Diablo ⚖️ (Steelman)")
            return (self.current_model, "Abogado del Diablo ⚖️")

        # 4. Modo Planificador Autónomo de Metas
        plan_triggers = [
            "planifica", "planificame", "planifícame", "crea un plan para", "diseña un plan para",
            "desglosa la meta", "desglosa este objetivo", "plan de acción para", "plan de accion para"
        ]
        if any(w in p_lower for w in plan_triggers):
            for pl in ["deepseek-r1", "phi4", "qwen2.5-coder", "llama3.2"]:
                for m in installed:
                    if pl in m.lower():
                        return (m, "Planificador Autónomo 🎯")
            return (self.current_model, "Planificador Autónomo 🎯")

        # 5. Código y Programación
        code_triggers = [
            "código", "codigo", "python", "flutter", "dart", "sql", "html", "css",
            "javascript", "typescript", "script", "función", "funcion", "error", "bug",
            "clase", "endpoint", "api", "refactoriza", "compila", "algoritmo", "git",
            "json", "yaml", "xml", "regex", "base de datos", "query", "postgres", "terminal", "powershell"
        ]
        if any(w in p_lower for w in code_triggers):
            for cd in ["qwen2.5-coder", "coder", "deepseek-coder"]:
                for m in installed:
                    if cd in m.lower():
                        return (m, "Código 💻 (Qwen Coder)")

        # 4. Razonamiento Profundo, Filosofía y Estrategia
        deep_triggers = [
            "analiza a fondo", "analizar a fondo", "filosofía", "filosofia", "estrategia",
            "por qué ocurre", "por que ocurre", "lógica", "logica", "demuestra",
            "debate", "dilema", "arquitectura", "explica detalladamente", "matemática",
            "matematica", "resuelve este problema", "paso a paso", "pros y contras"
        ]
        if any(w in p_lower for w in deep_triggers):
            for dp in ["deepseek-r1", "phi4", "llama-3.1-8b", "hermes3"]:
                for m in installed:
                    if dp in m.lower():
                        badge = "Razonamiento 🧠 (DeepSeek R1)" if "deepseek" in m.lower() else "Razonamiento 🧠 (Phi-4)"
                        return (m, badge)

        # 5. Por defecto: Modelo ágil estándar (Llama 3.2 3B o actual)
        for fg in ["llama3.2:3b", "llama3.2", "qwen2.5:3b"]:
            for m in installed:
                if fg in m.lower():
                    return (m, "Ágil ⚡ (Llama 3.2)")

        return (self.current_model, "Estándar ⚡")

    def clear_history(self):
        """Limpia el historial de conversación actual y documentos cargados."""
        self.history = []
        self.active_document = None
        self.active_document_name = None
        self._save_session()

    def load_document(self, filename: str, content: str):
        """Carga el contenido de un archivo arrastrado al asistente."""
        self.active_document_name = filename
        self.active_document = content
        logger.info(f"Documento cargado en F3nix: {filename} ({len(content)} caracteres)")

    def _log_activity(self, category: str, action: str, details: str = ""):
        """Emite eventos al registro de actividad en tiempo real del agente."""
        if self.on_activity_callback:
            try:
                self.on_activity_callback(category, action, details)
            except Exception as e:
                logger.error(f"Error emitiendo actividad del agente: {e}")

    def _check_system_tools(self, prompt: str) -> Optional[str]:
        """
        Intercepta comandos directos del sistema F3NIX (memoria, telemetría, hora, apps, temporizadores).
        """
        p_lower = prompt.lower().strip()

        # 1. Comandos de Memoria Persistente (Hermes Vault)
        # 1a. Guardar nuevo recuerdo: "recuerda que...", "guarda en tu memoria que..."
        memory_prefixes = [
            "recuerda que ", "recuerda: ",
            "guarda en tu memoria que ", "guarda en memoria que ",
            "anota que ", "aprende que ", "toma nota de que "
        ]
        for pref in memory_prefixes:
            if p_lower.startswith(pref):
                fact_text = prompt[len(pref):].strip(" .!¡¿?")
                if fact_text:
                    self.memory.add_fact(fact_text)
                    self._log_activity("Memoria", "Nuevo Recuerdo Guardado", fact_text)
                    return f"Entendido, Fenix. He grabado en mi memoria permanente: «{fact_text}»."

        # 1b. Consultar memoria: "¿qué recuerdas sobre mí?", "¿cuál es tu memoria?"
        memory_query_triggers = [
            "qué recuerdas sobre mí", "que recuerdas sobre mi",
            "qué recuerdas", "que recuerdas",
            "cuál es tu memoria", "cual es tu memoria",
            "qué tienes en memoria", "que tienes en memoria",
            "enséñame tu memoria", "ensename tu memoria"
        ]
        if any(mq in p_lower for mq in memory_query_triggers):
            self._log_activity("Memoria", "Consulta de Memoria Vault", "Lectura de hechos y perfil")
            facts = self.memory.data.get("facts", [])
            user_name = self.memory.data.get("user_name", "Fenix")
            role = self.memory.data.get("role", "Desarrollador")
            if not facts:
                return f"Tengo registrado que tu nombre es {user_name} ({role}), pero aún no tengo recuerdos adicionales anotados."
            bullet_points = "\n".join([f"• [{f.get('date', '')}] {f.get('text')}" for f in facts[-8:]])
            return f"Esto es lo que tengo grabado en mi memoria persistente sobre ti ({user_name}):\n\n{bullet_points}"

        # 2. Telemetría de hardware
        telemetry_triggers = ["cómo está el sistema", "estado del sistema", "telemetría", "diagnóstico del sistema", "cómo está la pc", "uso de ram", "uso de cpu"]
        if any(t in p_lower for t in telemetry_triggers):
            self._log_activity("Sistema", "Lectura de Telemetría", "CPU, RAM y Discos")
            return F3nixTools.get_system_telemetry()

        # 3. Hora y fecha en tiempo real
        time_triggers = ["qué hora es", "qué hora tienes", "qué fecha es", "en qué día estamos", "dime la hora"]
        if any(t in p_lower for t in time_triggers):
            self._log_activity("Sistema", "Consulta Horaria", "Hora y Fecha actual")
            return F3nixTools.get_time_and_date()

        # 4. Temporizadores / Pomodoro por voz
        timer_match = re.search(r'(?:pomodoro|temporizador|avísame en|alarma de|cuenta regresiva de)\s*(?:de)?\s*(\d+(?:\.\d+)?)\s*(minutos?|min|segundos?|seg)?', p_lower)
        if timer_match:
            qty = float(timer_match.group(1))
            unit = timer_match.group(2) or "min"
            minutes = qty if "seg" not in unit else qty / 60.0

            label = "Pomodoro" if "pomodoro" in p_lower else "Alarma programada"
            callback = self.on_timer_finished_callback or (lambda l: None)
            self._log_activity("Herramientas", "Temporizador Creado", f"{label} para {minutes:.1f} min")
            return F3nixTools.start_timer(minutes, label, callback)

        # 5. Apertura de programas
        if p_lower.startswith("abre ") or p_lower.startswith("abrir ") or p_lower.startswith("inicia "):
            app_target = p_lower.replace("abre ", "").replace("abrir ", "").replace("inicia ", "").strip()
            self._log_activity("Herramientas", "Lanzamiento de App", app_target)
            return F3nixTools.open_application(app_target)

        # 5b. Piloto Automático: Sincronización con GitHub
        github_triggers = [
            "sube a github", "subir a github", "sube el código a github", "subir el código a github",
            "sube mi código a github", "sube los cambios a github", "sincroniza con github",
            "sincronizar con github", "haz git push", "git push", "actualiza el repositorio",
            "subir cambios a github"
        ]
        if any(gt in p_lower for gt in github_triggers):
            commit_msg = None
            msg_match = re.search(r'(?:con mensaje|mensaje|comentario)\s+["«\']?([^"»\']+)["«\']?', prompt, re.IGNORECASE)
            if msg_match:
                commit_msg = msg_match.group(1).strip()
            self._log_activity("Piloto Automático", "GitHub Sync", commit_msg or "Automático")
            return F3nixTools.sync_github(commit_message=commit_msg)

        # 5c. Piloto Automático: Crear carpetas en el escritorio
        folder_triggers = [
            "crea una carpeta en el escritorio llamada", "crear una carpeta en el escritorio llamada",
            "crea una carpeta en el escritorio", "crear carpeta en el escritorio",
            "crea una carpeta llamada", "crear una carpeta llamada"
        ]
        for ft in folder_triggers:
            if ft in p_lower:
                idx = p_lower.find(ft)
                folder_name = prompt[idx + len(ft):].strip(" :,-'\"«»")
                if not folder_name:
                    folder_name = "Nueva_Carpeta_F3NIX"
                self._log_activity("Piloto Automático", "Crear Carpeta", folder_name)
                return F3nixTools.create_desktop_folder(folder_name)

        # 6. Crear notas en el escritorio de Windows
        note_triggers = [
            "crea una nota en el escritorio", "crear nota en el escritorio",
            "anota en el escritorio", "guarda una nota en el escritorio",
            "nota en el escritorio", "crear una nota con", "crea una nota con"
        ]
        for nt in note_triggers:
            if nt in p_lower:
                idx = p_lower.find(nt)
                remainder = prompt[idx + len(nt):].strip(" :,-")
                if remainder.lower().startswith("con "):
                    remainder = remainder[4:].strip()
                title = "Nota_F3NIX"
                m_title = re.search(r'(?:titulada|llamada)\s+([^\s,]+)', remainder, re.IGNORECASE)
                if m_title:
                    title = m_title.group(1)
                self._log_activity("Sistema", "Nota en Escritorio", title)
                return F3nixTools.create_desktop_note(title=title, content=remainder or "Nota creada por F3NIX")

        # 7. Espacio en disco y almacenamiento
        disk_triggers = [
            "espacio libre", "espacio en disco", "espacio en el disco", "cuánto espacio",
            "cuanto espacio", "almacenamiento libre", "disco d", "disco c", "estado de discos"
        ]
        if any(dt in p_lower for dt in disk_triggers) and ("disco" in p_lower or "espacio" in p_lower or "almacenamiento" in p_lower or "gigas" in p_lower):
            drive = None
            if "disco d" in p_lower or "en d" in p_lower:
                drive = "D"
            elif "disco c" in p_lower or "en c" in p_lower:
                drive = "C"
            self._log_activity("Sistema", "Lectura de Discos", drive or "Todos")
            return F3nixTools.get_disk_space_info(drive)

        # 8. Cierre de programas
        close_triggers = ["cierra ", "cerrar ", "termina ", "finaliza "]
        for ct in close_triggers:
            if p_lower.startswith(ct):
                app_target = p_lower[len(ct):].strip(" .!")
                self._log_activity("Sistema", "Cierre de App", app_target)
                return F3nixTools.close_application(app_target)

        # 9. Control de volumen de audio
        volume_triggers = [
            "silencia el volumen", "silencia el audio", "mutea", "mutear",
            "sube el volumen", "subir volumen", "baja el volumen", "bajar volumen",
            "volumen al máximo", "silenciar volumen", "silenciar audio"
        ]
        if any(vt in p_lower for vt in volume_triggers) or ("volumen" in p_lower and ("sub" in p_lower or "baj" in p_lower or "mute" in p_lower or "silenci" in p_lower)):
            self._log_activity("Sistema", "Control de Volumen", prompt)
            return F3nixTools.set_system_volume(prompt)

        # 10. Búsqueda y apertura rápida de archivos locales ("busca el archivo...", "abre el archivo...")
        search_file_triggers = [
            "busca el archivo", "buscar el archivo", "busca en mis archivos", "dónde está el archivo",
            "donde esta el archivo", "dónde guardé el archivo", "donde guarde el archivo",
            "dónde guardé", "donde guarde", "encuentra el archivo", "localiza el archivo"
        ]
        open_file_triggers = ["abre el archivo", "abrir el archivo", "abre el documento", "abrir el documento"]

        is_open_file = any(p_lower.startswith(oft) for oft in open_file_triggers)
        is_search_file = any(sft in p_lower for sft in search_file_triggers)

        if is_open_file or is_search_file:
            from core.file_searcher import FileSearcher
            fs = FileSearcher()
            target_query = p_lower
            for trg in (open_file_triggers if is_open_file else search_file_triggers):
                if trg in target_query:
                    target_query = target_query.replace(trg, "")
            target_query = target_query.strip(" :.-¿?¡!")
            if not target_query:
                target_query = prompt.strip()

            self._log_activity("Archivos", "Búsqueda Local", target_query)
            results = fs.search(target_query, max_results=3)

            if not results:
                return f"No encontré ningún archivo que coincida con «{target_query}» en tus rutas principales de Windows."

            if is_open_file:
                top = results[0]
                opened = FileSearcher.open_file(top["path"])
                if opened:
                    return f"He abierto el archivo «{top['name']}» en tu pantalla, Fenix."
                else:
                    FileSearcher.reveal_in_explorer(top["path"])
                    return f"He abierto la carpeta contenedora de «{top['name']}» en el Explorador de Windows."

            lines = [f"He encontrado los siguientes archivos para «{target_query}» en tu sistema:"]
            for r in results:
                size_str = f"({r['size_kb']} KB)" if not r["is_dir"] else "(Carpeta)"
                lines.append(f"• {r['name']} {size_str} — {r['path']}")
            lines.append("\nPuedes decir 'abre el archivo [nombre]' para abrirlo de inmediato.")
            return "\n".join(lines)

        # 11. Briefing Ejecutivo del Día ("Dame mi reporte", "Reporte de comandante")
        briefing_triggers = [
            "dame mi reporte", "reporte del día", "reporte del dia", "briefing del día", "briefing del dia",
            "briefing", "buenos días fenix", "buenos dias fenix", "cómo pinta el día", "como pinta el dia",
            "resumen del día", "resumen del dia", "reporte de comandante"
        ]
        if any(bt in p_lower for bt in briefing_triggers):
            self._log_activity("Sistema", "Briefing Ejecutivo", "Compilación de telemetría y metas")
            return F3nixTools.generate_executive_briefing(
                user_name=self.memory.get_user_name(),
                salutation=self.memory.get_salutation(),
                task_manager=self.task_manager
            )

        # 12. Rutinas y Macros por Voz ("Modo programación", "Modo enfoque", "Cierra mi jornada")
        routine_triggers = [
            "modo programación", "modo programacion", "modo desarrollo", "modo trabajo", "modo código", "modo codigo",
            "modo enfoque", "modo concentración", "modo concentracion", "modo estudio", "modo zen",
            "cierra mi jornada", "cerrar jornada", "fin de jornada", "terminar jornada", "cierra la jornada", "fin del día", "fin del dia"
        ]
        for rt in routine_triggers:
            if rt in p_lower:
                self._log_activity("Rutinas", "Ejecución de Macro", rt)
                def _on_turbo_toggle(val: bool):
                    self.turbo_mode = val
                return F3nixTools.execute_routine(
                    routine_name=rt,
                    user_name=self.memory.get_user_name(),
                    timer_callback=self.on_timer_finished_callback,
                    turbo_callback=_on_turbo_toggle,
                    task_manager=self.task_manager
                )

        # 13. Historial inteligente de portapapeles y recuperación
        clipboard_history_triggers = [
            "historial de portapapeles", "historial del portapapeles", "qué copié antes", "que copie antes",
            "qué tengo copiado", "que tengo copiado", "últimas cosas que copié", "ultimas cosas que copie",
            "recupera lo que copié", "recupera lo que copie", "qué copié", "que copie"
        ]
        if any(cht in p_lower for cht in clipboard_history_triggers):
            self._log_activity("Portapapeles", "Historial de Copiado", "Consulta de ClipboardRing")
            return F3nixTools.clipboard_ring.format_history_summary(limit=5)

        restore_clip_match = re.search(r'(?:copia|pega|restaura)\s+(?:el\s+)?(?:número|numero|item|texto)\s*(\d+)', p_lower)
        if restore_clip_match:
            idx = int(restore_clip_match.group(1))
            val = F3nixTools.clipboard_ring.get_item(idx)
            if val:
                try:
                    from PyQt6.QtWidgets import QApplication
                    app = QApplication.instance()
                    if app:
                        app.clipboard().setText(val)
                except Exception:
                    pass
                self._log_activity("Portapapeles", "Restauración de Elemento", f"Item #{idx}")
                return f"Elemento #{idx} restaurado en tu portapapeles:\n«{val[:80]}...»\nPuedes pegarlo con Ctrl+V."
            else:
                return f"No encontré el elemento #{idx} en tu historial reciente del portapapeles."

        # 14. Detección instantánea de ventana activa en primer plano (<0.1ms)
        window_triggers = [
            "qué ventana tengo abierta", "que ventana tengo abierta", "qué programa estoy usando",
            "que programa estoy usando", "dónde estoy", "donde estoy", "qué tengo abierto", "que tengo abierto"
        ]
        if any(wt in p_lower for wt in window_triggers):
            win = F3nixTools.get_active_window_info()
            self._log_activity("Sistema", "Ventana Activa", win['app_name'])
            return f"Estás en {win['app_name']} con la ventana «{win['title']}»."

        # 15. Consulta de sesión previa / Continuidad de conversación
        session_query_triggers = [
            "qué estábamos hablando", "que estabamos hablando",
            "de qué hablábamos", "de que hablabamos",
            "de qué estábamos hablando", "de que estabamos hablando",
            "en qué nos quedamos", "en que nos quedamos",
            "recuérdame la charla", "recuerdame la charla",
            "último tema", "ultimo tema"
        ]
        if any(sq in p_lower for sq in session_query_triggers):
            if not self.history:
                return "Aún no tenemos una conversación previa registrada en esta sesión, Comandante."
            recent = self.history[-4:]
            summary_lines = []
            for h in recent:
                speaker = "Tú dijiste" if h["role"] == "user" else "F3NIX respondió"
                content_snip = h["content"][:100] + ("..." if len(h["content"]) > 100 else "")
                summary_lines.append(f"• {speaker}: «{content_snip}»")
            self._log_activity("Memoria", "Consulta de Sesión", "Historial recuperado")
            return "Esto es de lo último que estábamos hablando antes:\n\n" + "\n".join(summary_lines)

        return None

    def chat(
        self,
        user_prompt: str,
        clipboard_text: Optional[str] = None,
        force_web_search: bool = False,
        turbo: Optional[bool] = None
    ) -> str:
        """
        Procesa la consulta del usuario garantizando no-solapamiento de inferencias en CPU.
        """
        if not self._chat_lock.acquire(blocking=False):
            return "Estoy procesando tu solicitud anterior. Por favor espera un momento..."
        try:
            return self._execute_chat(user_prompt, clipboard_text, force_web_search, turbo)
        finally:
            if self._chat_lock.locked():
                self._chat_lock.release()

    def chat_stream(
        self,
        user_prompt: str,
        clipboard_text: Optional[str] = None,
        force_web_search: bool = False,
        turbo: Optional[bool] = None,
        image_base64: Optional[str] = None
    ):
        """
        Generador en streaming (frase a frase y token a token) para inferencia instantánea.
        Emite:
          - {"type": "meta", "brain": str, "model": str}
          - {"type": "token", "content": str, "full_text": str}
          - {"type": "sentence", "content": str}
          - {"type": "error", "content": str}
        """
        if not self._chat_lock.acquire(blocking=False):
            yield {"type": "error", "content": "Estoy procesando tu solicitud anterior. Por favor espera un momento..."}
            return

        try:
            is_turbo = self.turbo_mode if turbo is None else bool(turbo)
            p_clean = user_prompt.lower()

            # 1. Herramientas directas de sistema y memoria
            tool_reply = self._check_system_tools(user_prompt)
            if tool_reply:
                yield {"type": "meta", "brain": "Sistema ⚙️", "model": "Windows Tools"}
                yield {"type": "token", "content": tool_reply, "full_text": tool_reply}
                yield {"type": "sentence", "content": tool_reply}
                self.history.append({"role": "user", "content": user_prompt})
                self.history.append({"role": "assistant", "content": tool_reply})
                self._save_session()
                return

            # 1b. Caché Instantáneo (< 1ms) para saludos, cortesías o consultas repetidas
            if not image_base64:
                user_name = self.memory.get_user_name()
                salutation = self.memory.get_salutation()
                instant_reply = InstantCache.get_instant_reply(user_prompt, user_name, salutation)
                if instant_reply:
                    yield {"type": "meta", "brain": "Instantáneo ⚡", "model": "Caché <1ms"}
                    yield {"type": "token", "content": instant_reply, "full_text": instant_reply}
                    yield {"type": "sentence", "content": instant_reply}
                    self.history.append({"role": "user", "content": user_prompt})
                    self.history.append({"role": "assistant", "content": instant_reply})
                    self._save_session()
                    return

            # 2. Visión Multimodal ("mira mi pantalla", etc.)
            vision_triggers = [
                "mira mi pantalla", "qué ves en mi pantalla", "que ves en mi pantalla",
                "analiza mi pantalla", "mira la pantalla", "captura de pantalla",
                "qué hay en mi pantalla", "que hay en mi pantalla",
                "qué ves aquí", "que ves aqui", "lee mi pantalla", "mira esto"
            ]
            needs_vision = bool(image_base64) or (
                any(vt in p_clean for vt in vision_triggers) and
                ("pantalla" in p_clean or "ves" in p_clean or "captura" in p_clean or "esto" in p_clean)
            )

            if needs_vision:
                base64_img = image_base64
                if not base64_img:
                    self._log_activity("Visión", "Captura de Pantalla", "Capturando interfaz en vivo...")
                    screen_data = F3nixTools.capture_screen()
                    if not screen_data.get("success"):
                        err_msg = f"No se pudo capturar la pantalla: {screen_data.get('error')}"
                        yield {"type": "error", "content": err_msg}
                        return
                    base64_img = screen_data.get("base64")

                vision_model, brain_badge = self.select_optimal_model(user_prompt, is_turbo=is_turbo, has_image=True)
                yield {"type": "meta", "brain": brain_badge, "model": vision_model}

                if "Visión" not in brain_badge:
                    no_vision_msg = (
                        "He capturado tu pantalla, pero no tienes un modelo de visión activo en Ollama.\n"
                        "💡 Ejecuta en tu terminal: 'ollama pull moondream' para habilitar visión instantánea."
                    )
                    yield {"type": "token", "content": no_vision_msg, "full_text": no_vision_msg}
                    yield {"type": "sentence", "content": no_vision_msg}
                    return

                self._log_activity("Visión", f"Inferencia Multimodal ({vision_model})", "Analizando imagen de pantalla...")
                
                # Moondream comprende mejor las instrucciones en inglés
                vision_prompt = "Describe in detail what is visible on this computer screen. Mention any open applications, windows, websites, desktop icons, text, code, or errors."
                if "error" in user_prompt.lower() or "fallo" in user_prompt.lower():
                    vision_prompt = "Look at this computer screen. Specifically focus on any error messages, warning dialogs, logs, or debugging information."

                payload_vision = {
                    "model": vision_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": vision_prompt,
                            "images": [base64_img]
                        }
                    ],
                    "stream": False,
                    "options": {"temperature": 0.2, "num_predict": 250}
                }

                raw_vision_desc = ""
                try:
                    res_v = requests.post(f"{self.base_url}/api/chat", json=payload_vision, timeout=45)
                    if res_v.status_code == 200:
                        raw_vision_desc = res_v.json().get("message", {}).get("content", "").strip()
                    else:
                        err = f"Error en inferencia de visión ({res_v.status_code}): {res_v.text}"
                        yield {"type": "error", "content": err}
                        return
                except Exception as e:
                    yield {"type": "error", "content": f"Error comunicando con modelo de visión: {e}"}
                    return

                if not raw_vision_desc:
                    raw_vision_desc = "A computer screen with open windows."

                # Sintetizar y traducir al español con Llama 3.2 para que F3NIX hable en español perfecto
                self._log_activity("Visión", "Síntesis en Español", "Traduciendo y explicando en español...")
                salutation = self.memory.get_salutation()
                synth_system_prompt = (
                    f"Eres F3NIX, el asistente de escritorio de IA de {salutation}.\n"
                    "DIRECTIVAS:\n"
                    "1. Responde SIEMPRE en español de forma natural, ágil y directa.\n"
                    "2. Explica claramente lo que el usuario tiene en pantalla basándote en la descripción visual proporcionada.\n"
                    "3. Sé conciso y útil (2 a 3 oraciones). NUNCA respondas en inglés."
                )

                synth_user_prompt = (
                    f"El usuario preguntó: «{user_prompt}».\n"
                    f"[Descripción visual detectada en la pantalla]:\n{raw_vision_desc}\n\n"
                    "Explícale en español qué tiene abierto y qué se observa en su pantalla."
                )

                payload_synth = {
                    "model": "llama3.2:3b",
                    "messages": [
                        {"role": "system", "content": synth_system_prompt},
                        {"role": "user", "content": synth_user_prompt}
                    ],
                    "stream": True,
                    "options": {"temperature": 0.5, "num_predict": 250, "repeat_penalty": 1.1}
                }

                accumulated = ""
                sent_buf = ""
                try:
                    with requests.post(f"{self.base_url}/api/chat", json=payload_synth, stream=True, timeout=60) as r:
                        if r.status_code == 200:
                            for line in r.iter_lines():
                                if not line:
                                    continue
                                chunk = json.loads(line.decode("utf-8"))
                                token = chunk.get("message", {}).get("content", "")
                                if token:
                                    accumulated += token
                                    sent_buf += token
                                    yield {"type": "token", "content": token, "full_text": accumulated}

                                    m = re.search(r'([.!?\n])(\s+|$)', sent_buf)
                                    if m and len(sent_buf.strip()) >= 15:
                                        idx = m.end()
                                        s_text = sent_buf[:idx].strip()
                                        if s_text:
                                            yield {"type": "sentence", "content": s_text}
                                        sent_buf = sent_buf[idx:]

                            if sent_buf.strip():
                                yield {"type": "sentence", "content": sent_buf.strip()}

                            self.history.append({"role": "user", "content": f"[Captura de Pantalla]: {user_prompt}"})
                            self.history.append({"role": "assistant", "content": accumulated.strip()})
                            return
                        else:
                            yield {"type": "sentence", "content": "No pude sintetizar la explicación de tu pantalla."}
                            return
                except Exception as e:
                    yield {"type": "error", "content": f"Error sintetizando visión en español: {e}"}
                    return

            # 3. Búsqueda Web
            search_triggers = [
                "busca en internet", "buscar en internet", "busca en la web", "buscar en la web",
                "noticias de", "precio de", "cotización de", "cotizacion de", "quién ganó", "quien gano",
                "quién es", "quien es", "dólar hoy", "dolar hoy", "clima hoy", "resultado de",
                "partido de hoy", "noticias hoy", "novedades de"
            ]
            needs_web_search = force_web_search or any(st in p_clean for st in search_triggers)
            web_context = ""
            if needs_web_search:
                clean_query = user_prompt
                for st in search_triggers:
                    clean_query = clean_query.replace(st, "")
                clean_query = clean_query.strip(" :¿?.,") or user_prompt
                import datetime
                today_str = datetime.datetime.now().strftime("%d/%m/%Y")
                self._log_activity("Búsqueda Web", "DuckDuckGo Live Search", clean_query)
                search_results = F3nixTools.search_web(clean_query)
                web_context = f"\n[DATOS DE INTERNET ({today_str})]:\n{search_results}\n"

            # 4. Contexto de documentos y portapapeles
            doc_context = ""
            if self.active_document:
                doc_context = f"\n[DOCUMENTO ADJUNTO: {self.active_document_name}]:\n{self.active_document[:2500]}\n"

            rag_context = ""
            if self.rag and self.rag.has_index():
                rag_snippets = self.rag.format_rag_context(user_prompt)
                if rag_snippets:
                    rag_context = f"\n{rag_snippets}\n"

            clip_context = ""
            if clipboard_text and len(clipboard_text.strip()) > 3:
                clip_triggers = ["portapapeles", "copiado", "este texto", "este código", "este codigo", "analiza esto"]
                if any(ct in p_clean for ct in clip_triggers) or len(clipboard_text.strip()) < 1000:
                    clip_context = f"\n[CONTENIDO DEL PORTAPAPELES]:\n{clipboard_text.strip()[:1500]}\n"

            # 5. Memoria en 2 Capas
            memory_triggers = [
                "recuerda", "acuerda", "sabes de mi", "sabes de mí", "quién soy", "quien soy",
                "mi proyecto", "mis proyectos", "mis metas", "mi vida", "consejo", "decisión",
                "decision", "opinas", "ayúdame a elegir", "ayudame a elegir", "plan", "rutina",
                "familia", "hijo", "entrenamiento", "finanzas", "bóveda", "boveda"
            ]
            needs_deep_memory = any(mt in p_clean for mt in memory_triggers)
            salutation = self.memory.get_salutation()
            if needs_deep_memory:
                memory_block = self.memory.get_memory_context()
            else:
                user_name = self.memory.get_user_name()
                tone = self.memory.data.get("tone_preference", "Directo, conciso y amigable")
                memory_block = f"[IDENTIDAD]:\n• Usuario: {user_name} ({salutation}) | Tono: {tone}"

            # 6. Detección de Modo Abogado del Diablo (Steelman) y Modo Planificador Autónomo
            steelman_triggers = [
                "abogado del diablo", "cuestiona mi idea", "cuestiona este plan", "critica mi plan",
                "critica mi propuesta", "destruye mi propuesta", "destruye este plan", "puntos ciegos",
                "contraargumenta", "steelman", "criterio firme", "evalúa este dilema", "evalua este dilema"
            ]
            is_steelman = any(st in p_clean for st in steelman_triggers)

            plan_triggers = [
                "planifica", "planificame", "planifícame", "crea un plan para", "diseña un plan para",
                "desglosa la meta", "desglosa este objetivo", "plan de acción para", "plan de accion para"
            ]
            is_plan = any(pt in p_clean for pt in plan_triggers)

            # Conciencia de ventana activa en primer plano (<0.1ms, zero-latency)
            win_info = F3nixTools.get_active_window_info()
            desktop_context = ""
            if win_info.get("app_name") not in ["Explorador de Windows", "Ventana de Windows"]:
                desktop_context = f"\n[VENTANA ACTIVA]: {win_info['app_name']} - «{win_info['title'][:60]}»\n"

            current_extras = f"{rag_context}{web_context}{doc_context}{clip_context}{desktop_context}"

            if is_steelman:
                system_prompt = self.reasoning.build_director_system_prompt(salutation)
                user_turn_content = self.reasoning.build_deliberation_prompt(user_prompt, salutation, context=current_extras)
            elif is_plan:
                system_prompt = (
                    f"Eres el Agente Planificador Autónomo F3NIX de {salutation}.\n"
                    "Tu misión es descomponer cualquier meta, objetivo o proyecto en exactamente 3 a 5 pasos secuenciales y accionables.\n"
                    "REGLAS DE FORMATO OBLIGATORIAS:\n"
                    "1. Cada paso debe comenzar estrictamente con el patrón: [PASO X: Título concreto de la tarea]\n"
                    "2. Debajo de cada etiqueta, explica en 1 a 2 oraciones qué debe ejecutarse.\n"
                    "3. Concluye con un resumen motivador indicando por qué paso comenzar hoy.\n"
                    f"{memory_block}"
                )
                user_turn_content = f"{current_extras}[META A PLANIFICAR]:\n{user_prompt}" if current_extras.strip() else user_prompt
            else:
                system_prompt = (
                    f"Eres F3NIX, el asistente de escritorio de IA para Windows 11 de {salutation}.\n"
                    "DIRECTIVAS FUNDAMENTALES:\n"
                    "1. Responde SIEMPRE en español de forma natural, ágil y profesional.\n"
                    "2. CONCISIÓN: Para saludos ('hola', 'qué tal') o charlas informales, responde de forma breve y amigable (1 a 2 oraciones).\n"
                    "3. PRECISIÓN: Si te solicitan explicaciones técnicas, código o planes, sé claro, estructurado y directo al grano.\n\n"
                    f"{memory_block}"
                )
                user_turn_content = f"{current_extras}[CONSULTA]:\n{user_prompt}" if current_extras.strip() else user_prompt

            if not self.is_server_online():
                err = "Error: No se pudo conectar con Ollama. Asegúrate de que el servicio esté iniciado."
                yield {"type": "error", "content": err}
                return

            # Smart Router
            model_to_use, brain_badge = self.select_optimal_model(user_prompt, is_turbo=is_turbo, has_image=False)
            yield {"type": "meta", "brain": brain_badge, "model": model_to_use}

            has_external_context = bool(web_context.strip() or doc_context.strip() or rag_context.strip())
            is_deep_request = "Razonamiento" in brain_badge or "Código" in brain_badge or is_steelman

            if is_turbo:
                num_tokens = 90
                ctx_size = 1024
            elif is_steelman:
                num_tokens = 550
                ctx_size = 2048
            elif is_plan:
                num_tokens = 450
                ctx_size = 2048
            elif has_external_context:
                num_tokens = 600
                ctx_size = 2048
            elif is_deep_request:
                num_tokens = 400
                ctx_size = 2048
            else:
                num_tokens = 130
                ctx_size = 1536

            # Optimización de CPU para Intel Core i5 (4 núcleos físicos, num_ctx acotado y keep_alive 60m)
            options = {
                "temperature": 0.4 if is_turbo else 0.7,
                "num_predict": num_tokens,
                "repeat_penalty": 1.1,
                "num_thread": 4,
                "num_ctx": ctx_size,
                "top_k": 30
            }

            self._log_activity("Inferencia", f"Cerebro {model_to_use} ({brain_badge})", "Generando en streaming...")

            # Ventana deslizante para CPU: solo los últimos 4 turnos históricos para evitar sobrecarga en prefill
            recent_history = self.history[-4:] if len(self.history) > 4 else self.history
            messages = [{"role": "system", "content": system_prompt}]
            for turn in recent_history:
                messages.append(turn)
            messages.append({"role": "user", "content": user_turn_content})

            payload = {
                "model": model_to_use,
                "messages": messages,
                "stream": True,
                "keep_alive": "60m",
                "options": options
            }

            accumulated_text = ""
            accumulated_thought = ""
            clean_text = ""
            sentence_buffer = ""
            is_thinking = False

            try:
                with requests.post(f"{self.base_url}/api/chat", json=payload, stream=True, timeout=90) as response:
                    if response.status_code == 200:
                        for line in response.iter_lines():
                            if not line:
                                continue
                            chunk = json.loads(line.decode("utf-8"))
                            token = chunk.get("message", {}).get("content", "")
                            if not token:
                                continue

                            accumulated_text += token

                            # Detección de inicio de bloque de pensamiento <think>
                            if "<think>" in token or ("<think>" in accumulated_text and not is_thinking and "</think>" not in accumulated_text):
                                is_thinking = True

                            if is_thinking:
                                accumulated_thought += token
                                if "</think>" in accumulated_thought or "</think>" in token:
                                    is_thinking = False
                                    parts = accumulated_thought.split("</think>", 1)
                                    pure_thought = parts[0].replace("<think>", "").strip()
                                    after_thought = parts[1] if len(parts) > 1 else ""
                                    yield {"type": "thought", "content": pure_thought, "status": "completed"}
                                    if after_thought:
                                        clean_text += after_thought
                                        sentence_buffer += after_thought
                                        yield {"type": "token", "content": after_thought, "full_text": clean_text}
                                else:
                                    clean_chunk = token.replace("<think>", "")
                                    if clean_chunk:
                                        yield {
                                            "type": "thought_token",
                                            "content": clean_chunk,
                                            "thought_text": accumulated_thought.replace("<think>", "").strip()
                                        }
                                continue

                            # Flujo de respuesta limpia fuera de <think>
                            clean_text += token
                            sentence_buffer += token
                            yield {"type": "token", "content": token, "full_text": clean_text}

                            m = re.search(r'([.!?\n])(\s+|$)', sentence_buffer)
                            if m and len(sentence_buffer.strip()) >= 15:
                                idx = m.end()
                                candidate = sentence_buffer[:idx].strip()
                                if candidate:
                                    yield {"type": "sentence", "content": candidate}
                                sentence_buffer = sentence_buffer[idx:]

                        if sentence_buffer.strip():
                            yield {"type": "sentence", "content": sentence_buffer.strip()}

                        # Al terminar, si es planificación de metas, extraer pasos automáticamente y cargarlos en tareas
                        final_clean = clean_text.strip() if clean_text.strip() else re.sub(r'<think>[\s\S]*?</think>', '', accumulated_text).strip()
                        if is_plan and self.task_manager:
                            step_matches = re.findall(r'\[PASO \d+:\s*([^\]]+)\]', final_clean, re.IGNORECASE)
                            if step_matches:
                                self.task_manager.add_plan_steps(step_matches)
                                yield {"type": "plan_steps", "steps": step_matches}

                        # Auto-Memoria pasiva: extraer hechos del usuario
                        learned_fact = self.memory.auto_extract_facts(user_prompt)
                        if learned_fact:
                            self._log_activity("Memoria", "Auto-Memoria Aprendida", learned_fact)
                            yield {"type": "auto_memory", "fact": learned_fact}

                        self.history.append({"role": "user", "content": user_prompt})
                        self.history.append({"role": "assistant", "content": final_clean})
                        self._save_session()
                        InstantCache.put_cache(user_prompt, final_clean)
                        if len(self.history) > self.max_history_turns * 2:
                            self.history = self.history[-(self.max_history_turns * 2):]
                    else:
                        err = f"Error de Ollama ({response.status_code}): {response.text}"
                        logger.error(err)
                        yield {"type": "error", "content": "Hubo un problema al procesar la respuesta con el modelo seleccionado."}
            except requests.exceptions.Timeout:
                yield {"type": "error", "content": "La consulta tardó más de lo esperado en responder. Tu procesador puede estar saturado."}
            except Exception as e:
                logger.error(f"Error en streaming de IA: {e}")
                yield {"type": "error", "content": f"Ocurrió un error inesperado al consultar a la IA: {str(e)}"}

        finally:
            if self._chat_lock.locked():
                self._chat_lock.release()


    def _execute_chat(
        self,
        user_prompt: str,
        clipboard_text: Optional[str] = None,
        force_web_search: bool = False,
        turbo: Optional[bool] = None
    ) -> str:
        is_turbo = self.turbo_mode if turbo is None else bool(turbo)
        p_clean = user_prompt.lower()

        # 1. Herramientas directas de sistema y memoria
        tool_reply = self._check_system_tools(user_prompt)
        if tool_reply:
            self.history.append({"role": "user", "content": user_prompt})
            self.history.append({"role": "assistant", "content": tool_reply})
            return tool_reply

        # 1b. Caché Instantáneo (< 1ms) para saludos, cortesías o consultas repetidas
        user_name = self.memory.get_user_name()
        salutation = self.memory.get_salutation()
        instant_reply = InstantCache.get_instant_reply(user_prompt, user_name, salutation)
        if instant_reply:
            self.history.append({"role": "user", "content": user_prompt})
            self.history.append({"role": "assistant", "content": instant_reply})
            return instant_reply

        # 2. Visión de Pantalla Multimodal ("mira mi pantalla", "qué ves en mi pantalla")
        vision_triggers = [
            "mira mi pantalla", "qué ves en mi pantalla", "que ves en mi pantalla",
            "analiza mi pantalla", "mira la pantalla", "captura de pantalla",
            "ayúdame con mi pantalla", "ayudame con mi pantalla",
            "qué hay en mi pantalla", "que hay en mi pantalla",
            "qué ves aquí", "que ves aqui", "lee mi pantalla", "qué ves", "que ves"
        ]
        if any(vt in p_clean for vt in vision_triggers) and ("pantalla" in p_clean or "ves" in p_clean or "captura" in p_clean):
            self._log_activity("Visión", "Captura de Pantalla", "Capturando y analizando interfaz en vivo...")
            screen_data = F3nixTools.capture_screen()
            if not screen_data.get("success"):
                return f"No se pudo capturar la pantalla: {screen_data.get('error')}"

            base64_img = screen_data.get("base64")

            # Detectar si el modelo actual o alguno instalado soporta visión
            installed = self.list_installed_models()
            vision_keywords = ["vision", "llava", "moondream", "minicpm", "bakllava"]

            def is_vision(m_name: str) -> bool:
                return any(k in m_name.lower() for k in vision_keywords)

            vision_model = None
            if is_vision(self.current_model):
                vision_model = self.current_model
            else:
                for candidate in installed:
                    if is_vision(candidate):
                        vision_model = candidate
                        break

            if vision_model:
                self._log_activity("Visión", f"Inferencia Multimodal ({vision_model})", "Enviando imagen a Ollama...")
                vision_prompt = (
                    f"Estás viendo una captura en tiempo real de la pantalla del usuario ({self.memory.data.get('user_name', 'Fenix')}). "
                    f"Consulta del usuario: «{user_prompt}». "
                    f"Describe concisamente lo que ves en la pantalla y proporciona una respuesta clara y directa en español."
                )
                payload = {
                    "model": vision_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": vision_prompt,
                            "images": [base64_img]
                        }
                    ],
                    "stream": False,
                    "options": {
                        "temperature": 0.4,
                        "num_predict": 300,
                        "num_ctx": 2048
                    }
                }
                try:
                    res = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=60)
                    if res.status_code == 200:
                        analysis = res.json().get("message", {}).get("content", "")
                        self.history.append({"role": "user", "content": f"[Captura de Pantalla enviada]: {user_prompt}"})
                        self.history.append({"role": "assistant", "content": analysis})
                        self._log_activity("Visión", "Análisis Completado", f"{len(analysis)} caracteres generados")
                        return analysis
                    else:
                        logger.error(f"Error en inferencia de visión: {res.status_code} {res.text}")
                except Exception as e:
                    logger.error(f"Error consultando modelo de visión: {e}")

            return (
                "He capturado tu pantalla en tiempo real con éxito. Sin embargo, tu cerebro actual "
                f"('{self.current_model}') es de sólo texto y no puede procesar imágenes directamente.\n\n"
                "👁️ **Para que F3NIX pueda 'ver' tu pantalla con sus propios ojos:**\n"
                "Necesitas un modelo con visión como **Moondream 2** (1.7 GB, súper ligero) o **LLaVA 7B**.\n"
                "👉 Abre el menú de F3NIX y selecciona **'📥 Instalar Nuevos Cerebros'** para descargarlo."
            )

        # 3. Búsqueda Web en Vivo (DuckDuckGo Lite)
        search_triggers = [
            "busca en internet", "buscar en internet", "busca en la web", "buscar en la web",
            "noticias de", "precio de", "cotización de", "cotizacion de", "quién ganó", "quien gano",
            "quién es", "quien es", "dólar hoy", "dolar hoy", "clima hoy", "resultado de",
            "partido de hoy", "noticias hoy", "novedades de"
        ]
        needs_web_search = force_web_search or any(st in p_clean for st in search_triggers)

        web_context = ""
        if needs_web_search:
            clean_query = user_prompt
            for st in search_triggers:
                clean_query = clean_query.replace(st, "")
            clean_query = clean_query.strip(" :¿?.,")
            if not clean_query:
                clean_query = user_prompt

            import datetime
            today_str = datetime.datetime.now().strftime("%d/%m/%Y")
            logger.info(f"Ejecutando búsqueda web DuckDuckGo para: {clean_query}")
            self._log_activity("Búsqueda Web", "DuckDuckGo Live Search", clean_query)
            search_results = F3nixTools.search_web(clean_query)
            web_context = f"\n[DATOS DE INTERNET ({today_str})]:\n{search_results}\n"

        # 4. Inyección inteligente de Documento cargado (Drag & Drop)
        doc_context = ""
        if self.active_document:
            doc_snippet = self.active_document[:2500]
            doc_context = f"\n[DOCUMENTO CARGADO ({self.active_document_name})]:\n```\n{doc_snippet}\n```\n"
            self._log_activity("Documentos", "Inyección de Contexto", self.active_document_name or "Archivo")

        # 4b. Inyección inteligente de RAG Local
        rag_context = ""
        if self.rag and self.rag.has_index():
            rag_snippets = self.rag.format_rag_context(user_prompt)
            if rag_snippets:
                rag_context = f"\n{rag_snippets}\n"
                self._log_activity("RAG Local", "Búsqueda en Proyecto", f"Contexto de {self.rag.current_folder_name}")

        # 5. Inyección inteligente de Portapapeles
        clip_context = ""
        clipboard_triggers = [
            "copié", "copie", "portapapeles", "código", "codigo",
            "analiza esto", "revisa esto", "explica esto", "corrige esto",
            "qué ves en el portapapeles", "pegué esto", "lo copiado"
        ]
        has_clipboard_trigger = any(t in p_clean for t in clipboard_triggers)

        if has_clipboard_trigger and clipboard_text and clipboard_text.strip():
            clip_snippet = clipboard_text.strip()
            if len(clip_snippet) > 2000:
                clip_snippet = clip_snippet[:1990] + "\n... [Texto recortado]"
            clip_context = f"\n[PORTAPAPELES DE WINDOWS]:\n```\n{clip_snippet}\n```\n"
            self._log_activity("Portapapeles", "Lectura de Texto Copiado", f"{len(clip_snippet)} caracteres")

        # 6. Memoria Inteligente en 2 Capas (Ultra-Ligera por defecto, Profunda bajo demanda)
        memory_triggers = [
            "recuerda", "acuerda", "sabes de mi", "sabes de mí", "quién soy", "quien soy",
            "mi proyecto", "mis proyectos", "mis metas", "mi vida", "consejo", "decisión",
            "decision", "opinas", "ayúdame a elegir", "ayudame a elegir", "plan", "rutina",
            "familia", "hijo", "entrenamiento", "finanzas", "bóveda", "boveda"
        ]
        needs_deep_memory = any(mt in p_clean for mt in memory_triggers)

        salutation = self.memory.get_salutation()
        if needs_deep_memory:
            memory_block = self.memory.get_memory_context()
        else:
            user_name = self.memory.get_user_name()
            tone = self.memory.data.get("tone_preference", "Directo, conciso y amigable")
            memory_block = f"[IDENTIDAD]:\n• Usuario: {user_name} ({salutation}) | Tono: {tone}"

        # 6b. Detección de Modo Abogado del Diablo (Steelman) y Modo Planificador Autónomo
        steelman_triggers = [
            "abogado del diablo", "cuestiona mi idea", "cuestiona este plan", "critica mi plan",
            "critica mi propuesta", "destruye mi propuesta", "destruye este plan", "puntos ciegos",
            "contraargumenta", "steelman", "criterio firme", "evalúa este dilema", "evalua este dilema"
        ]
        is_steelman = any(st in p_clean for st in steelman_triggers)

        plan_triggers = [
            "planifica", "planificame", "planifícame", "crea un plan para", "diseña un plan para",
            "desglosa la meta", "desglosa este objetivo", "plan de acción para", "plan de accion para"
        ]
        is_plan = any(pt in p_clean for pt in plan_triggers)

        # Conciencia de ventana activa en primer plano (<0.1ms, zero-latency)
        win_info = F3nixTools.get_active_window_info()
        desktop_context = ""
        if win_info.get("app_name") not in ["Explorador de Windows", "Ventana de Windows"]:
            desktop_context = f"\n[VENTANA ACTIVA]: {win_info['app_name']} - «{win_info['title'][:60]}»\n"

        current_extras = f"{rag_context}{web_context}{doc_context}{clip_context}{desktop_context}"

        if is_steelman:
            system_prompt = self.reasoning.build_director_system_prompt(salutation)
            user_turn_content = self.reasoning.build_deliberation_prompt(user_prompt, salutation, context=current_extras)
        elif is_plan:
            system_prompt = (
                f"Eres el Agente Planificador Autónomo F3NIX de {salutation}.\n"
                "Tu misión es descomponer cualquier meta, objetivo o proyecto en exactamente 3 a 5 pasos secuenciales y accionables.\n"
                "REGLAS DE FORMATO OBLIGATORIAS:\n"
                "1. Cada paso debe comenzar estrictamente con el patrón: [PASO X: Título concreto de la tarea]\n"
                "2. Debajo de cada etiqueta, explica en 1 a 2 oraciones qué debe ejecutarse.\n"
                "3. Concluye con un resumen motivador indicando por qué paso comenzar hoy.\n"
                f"{memory_block}"
            )
            user_turn_content = f"{current_extras}[META A PLANIFICAR]:\n{user_prompt}" if current_extras.strip() else user_prompt
        else:
            system_prompt = (
                f"Eres F3NIX, el asistente de escritorio de IA para Windows 11 de {salutation}.\n"
                "DIRECTIVAS FUNDAMENTALES:\n"
                "1. Responde SIEMPRE en español de forma natural, ágil y profesional.\n"
                "2. CONCISIÓN: Para saludos ('hola', 'qué tal') o charlas informales, responde de forma breve y amigable (1 a 2 oraciones). NUNCA generes respuestas excesivamente largas o innecesarias ante un simple saludo.\n"
                "3. PRECISIÓN: Si te solicitan explicaciones técnicas, código o planes, sé claro, estructurado y directo al grano.\n\n"
                f"{memory_block}"
            )
            user_turn_content = f"{current_extras}[CONSULTA]:\n{user_prompt}" if current_extras.strip() else user_prompt

        if not self.is_server_online():
            return "Error: No se pudo conectar con Ollama. Asegúrate de que el servicio esté iniciado en tu sistema."

        # Detección de necesidad de profundidad técnica o concisión rápida
        is_deep_request = any(w in p_clean for w in [
            "código", "codigo", "explica a fondo", "detalle", "detallado",
            "paso a paso", "analiza a fondo", "escribe un", "redacta un", "estrategia"
        ]) or is_steelman

        # Detectar si hay contextos externos (web, documentos, RAG) que generan respuestas largas
        has_external_context = bool(
            (web_context and web_context.strip()) or
            (doc_context and doc_context.strip()) or
            (rag_context and rag_context.strip())
        )

        # num_predict: más tokens cuando hay contexto externo para no cortar la respuesta a mitad
        if is_turbo:
            num_tokens = 90
            ctx_size = 1024
        elif is_steelman:
            num_tokens = 550
            ctx_size = 2048
        elif is_plan:
            num_tokens = 450
            ctx_size = 2048
        elif has_external_context:
            num_tokens = 600
            ctx_size = 2048
        elif is_deep_request:
            num_tokens = 400
            ctx_size = 2048
        else:
            num_tokens = 130
            ctx_size = 1536

        # Smart Router: Selección óptima del modelo
        model_to_use, brain_badge = self.select_optimal_model(user_prompt, is_turbo=is_turbo, has_image=False)
        self._log_activity("Inferencia", f"Cerebro {model_to_use} ({brain_badge})", "Generando respuesta...")

        # Optimización de CPU para Intel Core i5
        options = {
            "temperature": 0.4 if is_turbo else 0.7,
            "num_predict": num_tokens,
            "repeat_penalty": 1.1,
            "num_thread": 4,
            "num_ctx": ctx_size,
            "top_k": 30
        }

        # Enviar estructura limpia con ventana deslizante para no inflar prefill en CPU
        recent_history = self.history[-4:] if len(self.history) > 4 else self.history
        messages = [{"role": "system", "content": system_prompt}]
        for turn in recent_history:
            messages.append(turn)
        messages.append({"role": "user", "content": user_turn_content})

        payload = {
            "model": model_to_use,
            "messages": messages,
            "stream": False,
            "keep_alive": "60m",
            "options": options
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=90
            )

            if response.status_code == 200:
                result = response.json()
                raw_message = result.get("message", {}).get("content", "").strip()
                # Limpiar cualquier residuo de etiquetas <think>...</think>
                assistant_message = re.sub(r'<think>[\s\S]*?</think>', '', raw_message).strip()

                # Si es un plan de acción, extraer pasos automáticamente y cargarlos en tareas
                if is_plan and self.task_manager:
                    step_matches = re.findall(r'\[PASO \d+:\s*([^\]]+)\]', assistant_message, re.IGNORECASE)
                    if step_matches:
                        self.task_manager.add_plan_steps(step_matches)

                # Auto-Memoria pasiva: extraer hechos del usuario
                learned_fact = self.memory.auto_extract_facts(user_prompt)
                if learned_fact:
                    self._log_activity("Memoria", "Auto-Memoria Aprendida", learned_fact)

                # Guardar en historial solo el diálogo limpio sin inflar contexto
                self.history.append({"role": "user", "content": user_prompt})
                self.history.append({"role": "assistant", "content": assistant_message})
                self._save_session()
                InstantCache.put_cache(user_prompt, assistant_message)
                if len(self.history) > self.max_history_turns * 2:
                    self.history = self.history[-(self.max_history_turns * 2):]
                return assistant_message
            else:
                error_msg = f"Error de Ollama ({response.status_code}): {response.text}"
                logger.error(error_msg)
                return "Hubo un problema al procesar la respuesta con el modelo seleccionado."
        except requests.exceptions.Timeout:
            return "La consulta tardó más de lo esperado en responder. Tu procesador puede estar saturado."
        except Exception as e:
            logger.error(f"Error en consulta a la IA: {e}")
            return f"Ocurrió un error inesperado al consultar a la IA: {str(e)}"
