import os
import json
import uuid
import re
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

TASKS_FILE = "f3nix_tasks.json"

class TaskManager:
    """
    Gestor de tareas pendientes (To-Do List) persistente para el HUD de F3NIX.
    Permite crear, tachar, eliminar tareas y parsear órdenes por voz.
    """
    def __init__(self, filepath: str = TASKS_FILE):
        self.filepath = filepath
        self.tasks: List[Dict[str, Any]] = []
        self._load_tasks()

    def _load_tasks(self):
        """Carga las tareas guardadas en el archivo JSON."""
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    self.tasks = json.load(f)
            except Exception as e:
                logger.error(f"Error cargando tareas desde {self.filepath}: {e}")
                self.tasks = []
        else:
            self.tasks = []
            self._save_tasks()

    def _save_tasks(self):
        """Guarda las tareas actuales en el archivo JSON."""
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.tasks, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error guardando tareas en {self.filepath}: {e}")

    def add_task(self, text: str) -> Dict[str, Any]:
        """Agrega una nueva tarea a la lista."""
        clean_text = text.strip()
        if not clean_text:
            return {}

        task = {
            "id": str(uuid.uuid4())[:8],
            "text": clean_text,
            "done": False,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        self.tasks.insert(0, task)
        self._save_tasks()
        return task

    def toggle_task(self, task_id: str) -> Optional[bool]:
        """Alterna el estado completado/pendiente de una tarea."""
        for t in self.tasks:
            if t["id"] == task_id:
                t["done"] = not t["done"]
                self._save_tasks()
                return t["done"]
        return None

    def delete_task(self, task_id: str) -> bool:
        """Elimina una tarea por su ID."""
        initial_len = len(self.tasks)
        self.tasks = [t for t in self.tasks if t["id"] != task_id]
        if len(self.tasks) < initial_len:
            self._save_tasks()
            return True
        return False

    def clear_completed(self) -> int:
        """Elimina todas las tareas marcadas como completadas."""
        initial_len = len(self.tasks)
        self.tasks = [t for t in self.tasks if not t.get("done", False)]
        removed = initial_len - len(self.tasks)
        if removed > 0:
            self._save_tasks()
        return removed

    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """Devuelve todas las tareas."""
        return self.tasks

    def add_plan_steps(self, steps: List[str]) -> List[Dict[str, Any]]:
        """Añade una secuencia de pasos ordenados a la lista de tareas preservando el orden 1..N."""
        created = []
        for step in reversed(steps):
            clean = step.strip()
            if clean:
                t = self.add_task(clean)
                created.append(t)
        return list(reversed(created))

    def get_active_count(self) -> int:
        """Devuelve el número de tareas pendientes (no completadas)."""
        return sum(1 for t in self.tasks if not t.get("done", False))

    @staticmethod
    def parse_voice_task(prompt: str) -> Optional[str]:
        """
        Detecta si el prompt contiene una instrucción de creación de tarea
        y extrae el contenido de la misma.
        Ejemplos:
          - 'anota la tarea revisar el servidor' -> 'revisar el servidor'
          - 'agrega una tarea: comprar café' -> 'comprar café'
          - 'recuérdame llamar a Juan mañana' -> 'llamar a Juan mañana'
          - 'tengo que pagar el hosting' -> 'pagar el hosting'
        """
        p_clean = prompt.strip()
        lower = p_clean.lower()

        patterns = [
            r"^(?:f3nix[,\s]+)?(?:agrega|añade|crea|anota|pon|guarda)\s+(?:una\s+|la\s+)?tarea(?:\s*:\s*|\s+que\s+sea\s+|\s+de\s+|\s+)(.+)$",
            r"^(?:f3nix[,\s]+)?(?:recuérdame|recuerdame)\s+(?:que\s+tengo\s+que\s+|que\s+|)(.+)$",
            r"^(?:f3nix[,\s]+)?tengo que\s+(.+)$",
            r"^(?:f3nix[,\s]+)?nueva tarea(?:\s*:\s*|\s+)(.+)$"
        ]

        for pat in patterns:
            m = re.match(pat, lower, re.IGNORECASE)
            if m:
                # Tomar el fragmento coincidente de la cadena original preservando mayúsculas
                span = m.span(1)
                task_content = p_clean[span[0]:span[1]].strip(" :.,¿?")
                if len(task_content) > 2:
                    return task_content

        return None
