import os
import sys
import psutil
import datetime
import subprocess
import threading
import time
import base64
import re
import logging
from typing import Optional, Dict, Any, Callable, List
from PIL import ImageGrab
import keyboard

logger = logging.getLogger(__name__)

class TimerManager:
    """
    Gestiona temporizadores, pomodoros y recordatorios en segundo plano.
    """
    def __init__(self):
        self.active_timers = {}
        self._lock = threading.Lock()

    def set_timer(self, minutes: float, label: str, callback: Callable[[str], None]):
        seconds = int(minutes * 60)
        timer_id = f"timer_{int(time.time())}_{label}"

        def _worker():
            time.sleep(seconds)
            with self._lock:
                if timer_id in self.active_timers:
                    del self.active_timers[timer_id]
            callback(label)

        t = threading.Thread(target=_worker, daemon=True)
        with self._lock:
            self.active_timers[timer_id] = {
                "thread": t,
                "label": label,
                "minutes": minutes,
                "start": time.time()
            }
        t.start()
        return timer_id

timer_manager = TimerManager()


class ClipboardRing:
    """
    Historial inteligente del portapapeles (Time-Machine) para F3NIX.
    Almacena los últimos 15 elementos de texto copiados en la sesión.
    """
    def __init__(self, max_items: int = 15):
        self.max_items = max_items
        self.history: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def add(self, text: str) -> bool:
        clean = text.strip()
        if not clean or len(clean) < 2:
            return False
        with self._lock:
            # Si el texto ya es el más reciente, no duplicar consecutivamente
            if self.history and self.history[0]["content"] == clean:
                return False
            # Quitar si ya existía en otra posición para moverlo al frente
            self.history = [item for item in self.history if item["content"] != clean]
            now_str = datetime.datetime.now().strftime("%H:%M")
            preview = clean.replace("\n", " ")[:60] + ("..." if len(clean) > 60 else "")
            item = {
                "id": len(self.history) + 1,
                "content": clean,
                "preview": preview,
                "time": now_str,
                "length": len(clean)
            }
            self.history.insert(0, item)
            if len(self.history) > self.max_items:
                self.history = self.history[:self.max_items]
            # Renumerar de 1 a N
            for idx, h in enumerate(self.history, 1):
                h["id"] = idx
            return True

    def get_recent(self, limit: int = 5) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self.history[:limit])

    def get_item(self, index: int) -> Optional[str]:
        with self._lock:
            for item in self.history:
                if item["id"] == index:
                    return item["content"]
            return None

    def format_history_summary(self, limit: int = 5) -> str:
        with self._lock:
            if not self.history:
                return "Tu historial de portapapeles está vacío por ahora. Se irá llenando conforme copies texto con Ctrl+C."
            lines = ["📋 Historial reciente de tu portapapeles:"]
            for item in self.history[:limit]:
                lines.append(f"{item['id']}. [{item['time']}] «{item['preview']}» ({item['length']} caracteres)")
            lines.append("\nPuedes decir 'copia el número [X]' para restaurar cualquiera de ellos al portapapeles.")
            return "\n".join(lines)


clipboard_ring = ClipboardRing()

class F3nixTools:
    """
    Herramientas del sistema y control en tiempo real nativas de F3NIX.
    """
    @staticmethod
    def is_connected_to_internet() -> bool:
        """Verificación ultrarrápida (0.4s) de conectividad a internet."""
        import socket
        try:
            socket.setdefaulttimeout(0.4)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("1.1.1.1", 53))
            s.close()
            return True
        except Exception:
            return False

    @staticmethod
    def search_web(query: str, max_results: int = 4) -> str:
        """Busca información en tiempo real usando DDGS y fallbacks encadenados (DuckDuckGo + Wikipedia)."""
        if not F3nixTools.is_connected_to_internet():
            return f"No hay conexión a internet disponible para buscar «{query}»."

        # 1. Intento primario con ddgs / duckduckgo_search
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS

            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
                if results:
                    formatted = []
                    for i, r in enumerate(results, 1):
                        formatted.append(f"[{i}] {r.get('title', '')}\n{r.get('body', '')}\nFuente: {r.get('href', '')}")
                    return "\n\n".join(formatted)
        except Exception as e:
            logger.debug(f"DDGS no disponible o con límite: {e}")

        # 2. Fallback secundario: Wikipedia REST API en español (instantánea y enciclopédica)
        try:
            import urllib.parse
            import requests
            import re
            wiki_url = f"https://es.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&utf8=&format=json"
            rw = requests.get(wiki_url, headers={"User-Agent": "F3NIX_AI_Studio/1.0"}, timeout=4)
            if rw.status_code == 200:
                w_data = rw.json()
                search_res = w_data.get("query", {}).get("search", [])
                if search_res:
                    formatted = []
                    for i, item in enumerate(search_res[:max_results], 1):
                        title = item.get("title", "")
                        clean_snip = re.sub(r'<[^>]+>', '', item.get("snippet", "")).strip()
                        formatted.append(f"[{i}] {title}\n{clean_snip}\nFuente: https://es.wikipedia.org/wiki/{urllib.parse.quote(title)}")
                    if formatted:
                        return "\n\n".join(formatted)
        except Exception as w_err:
            logger.debug(f"Wikipedia fallback falló: {w_err}")

        # 3. Fallback terciario: DuckDuckGo Instant Answer API
        try:
            import urllib.parse
            import requests
            url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1"
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=4)
            if r.status_code == 200:
                data = r.json()
                abstract = data.get("AbstractText") or data.get("Abstract")
                source_url = data.get("AbstractURL", "")
                if abstract:
                    return f"[1] {data.get('Heading', query)}\n{abstract}\nFuente: {source_url}"
        except Exception as d_err:
            logger.debug(f"DDG Instant Answer falló: {d_err}")

        return f"No se pudieron obtener resultados de internet para '{query}' en este momento."

    @staticmethod
    def capture_screen(output_path: str = "screen_capture.jpg") -> Dict[str, Any]:
        """Toma una captura de pantalla usando PyQt6 o ImageGrab."""
        try:
            # 1. Prioridad: Captura mediante la sesión activa de PyQt6
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                screen = app.primaryScreen()
                if screen:
                    pixmap = screen.grabWindow(0)
                    pixmap.save(output_path, "JPEG", 80)
                    with open(output_path, "rb") as img_file:
                        b64_data = base64.b64encode(img_file.read()).decode("utf-8")
                    return {"success": True, "path": output_path, "base64": b64_data}

            # 2. Fallback: PIL ImageGrab
            screenshot = ImageGrab.grab()
            screenshot.thumbnail((1280, 720))
            screenshot.save(output_path, "JPEG", quality=80)

            with open(output_path, "rb") as img_file:
                b64_data = base64.b64encode(img_file.read()).decode("utf-8")

            return {
                "success": True,
                "path": output_path,
                "base64": b64_data
            }
        except Exception as e:
            logger.error(f"Error capturando pantalla: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def start_timer(minutes: float, label: str, on_finished_callback: Callable[[str], None]) -> str:
        """Inicia un temporizador o pomodoro."""
        timer_manager.set_timer(minutes, label, on_finished_callback)
        unit = "minuto" if minutes == 1 else "minutos"
        return f"Temporizador de {minutes} {unit} activado para: '{label}'."

    @staticmethod
    def type_into_active_window(text: str):
        """Escribe directamente donde esté parpadeando el cursor."""
        try:
            # Breve pausa para asegurar foco en la ventana destino
            time.sleep(0.3)
            keyboard.write(text, delay=0.01)
            return True
        except Exception as e:
            logger.error(f"Error escribiendo en ventana activa: {e}")
            return False

    @staticmethod
    def get_system_telemetry() -> str:
        """Obtiene métricas de CPU, RAM y almacenamiento en tiempo real."""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            ram = psutil.virtual_memory()
            ram_used_gb = round(ram.used / (1024 ** 3), 1)
            ram_total_gb = round(ram.total / (1024 ** 3), 1)
            ram_percent = ram.percent

            battery = psutil.sensors_battery()
            battery_str = f", Batería al {battery.percent}%" if battery else ""

            return (
                f"Telemetría F3NIX: CPU al {cpu_percent}%, "
                f"Memoria RAM al {ram_percent}% ({ram_used_gb} GB de {ram_total_gb} GB en uso){battery_str}. "
                f"Sistemas operando con normalidad."
            )
        except Exception as e:
            return f"No se pudieron leer los sensores del sistema: {e}"

    @staticmethod
    def get_time_and_date() -> str:
        """Devuelve la fecha y hora actual formateada."""
        now = datetime.datetime.now()
        dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
        meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
        dia_semana = dias[now.weekday()]
        mes = meses[now.month - 1]
        hora = now.strftime("%H:%M")
        return f"Son las {hora} horas del {dia_semana} {now.day} de {mes}."

    @staticmethod
    def open_application(app_name: str) -> str:
        """Abre aplicaciones comunes solicitadas por voz."""
        app_name_lower = app_name.lower().strip()
        common_apps = {
            "vscode": "code",
            "vs code": "code",
            "visual studio code": "code",
            "navegador": "start chrome || start msedge",
            "chrome": "chrome",
            "edge": "msedge",
            "terminal": "wt || powershell",
            "powershell": "powershell",
            "bloc de notas": "notepad",
            "notepad": "notepad",
            "calculadora": "calc",
            "explorador": "explorer"
        }

        for key, cmd in common_apps.items():
            if key in app_name_lower:
                try:
                    subprocess.Popen(cmd, shell=True)
                    return f"Abriendo {key} de inmediato, Fenix."
                except Exception as e:
                    return f"No pude iniciar la aplicación: {e}"

        return f"No reconozco la aplicación {app_name} para apertura automática."

    @staticmethod
    def create_desktop_note(title: str, content: str) -> str:
        """Crea un archivo de nota .txt en el escritorio de Windows."""
        try:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            if not os.path.exists(desktop):
                onedrive_desktop = os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop")
                if os.path.exists(onedrive_desktop):
                    desktop = onedrive_desktop
                else:
                    desktop = os.path.expanduser("~")

            clean_title = re.sub(r'[\\/*?:"<>|]', "", title).strip() or "Nota_F3NIX"
            filename = f"{clean_title}.txt"
            filepath = os.path.join(desktop, filename)

            base, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(filepath):
                filepath = os.path.join(desktop, f"{base}_{counter}{ext}")
                counter += 1

            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            full_text = f"=== NOTA F3NIX ({timestamp}) ===\n\n{content.strip()}\n"

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(full_text)

            return f"Nota guardada en tu escritorio: '{os.path.basename(filepath)}'."
        except Exception as e:
            logger.error(f"Error creando nota en escritorio: {e}")
            return f"No se pudo crear la nota en el escritorio: {e}"

    @staticmethod
    def get_disk_space_info(drive_letter: Optional[str] = None) -> str:
        """Devuelve el espacio libre y total en discos del sistema."""
        try:
            partitions = psutil.disk_partitions()
            results = []
            target = drive_letter.upper().strip(":\\/") if drive_letter else None

            for p in partitions:
                if "cdrom" in p.opts or p.fstype == "":
                    continue
                d_name = p.device.replace("\\", "")
                if target and target not in d_name:
                    continue
                try:
                    usage = psutil.disk_usage(p.mountpoint)
                    total_gb = round(usage.total / (1024 ** 3), 1)
                    free_gb = round(usage.free / (1024 ** 3), 1)
                    percent = usage.percent
                    results.append(f"Disco {d_name}: {free_gb} GB libres de {total_gb} GB ({percent}% en uso)")
                except (PermissionError, OSError):
                    continue

            if not results:
                return f"No se encontró información para el disco {drive_letter or 'solicitado'}."
            return " • ".join(results)
        except Exception as e:
            return f"Error consultando espacio en disco: {e}"

    @staticmethod
    def close_application(app_name: str) -> str:
        """Cierra procesos de aplicaciones solicitadas por el usuario."""
        target = app_name.lower().strip().replace(".exe", "")
        aliases = {
            "chrome": ["chrome"],
            "google chrome": ["chrome"],
            "edge": ["msedge"],
            "microsoft edge": ["msedge"],
            "bloc de notas": ["notepad"],
            "notepad": ["notepad"],
            "spotify": ["spotify"],
            "calculadora": ["calculatorapp", "calc"],
            "explorador": ["explorer"],
            "vscode": ["code"],
            "visual studio code": ["code"],
            "discord": ["discord"],
            "telegram": ["telegram"]
        }
        proc_names = aliases.get(target, [target])
        closed_count = 0

        for proc in psutil.process_iter(['name']):
            try:
                p_name = proc.info['name'].lower().replace(".exe", "")
                if any(cand in p_name for cand in proc_names):
                    proc.terminate()
                    closed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        if closed_count > 0:
            return f"He cerrado {app_name} ({closed_count} proceso(s) finalizados)."
        return f"No encontré ningún proceso activo para '{app_name}'."

    @staticmethod
    def set_system_volume(action_or_level: str) -> str:
        """Ajusta el volumen del sistema o silencia el audio en Windows usando comandos nativos."""
        action = action_or_level.lower().strip()
        try:
            if "mute" in action or "silenci" in action or "mutear" in action:
                cmd = "$wsh = New-Object -ComObject WScript.Shell; $wsh.SendKeys([char]173)"
                subprocess.run(["powershell", "-Command", cmd], capture_output=True, timeout=3)
                return "Audio silenciado / restaurado en Windows."
            elif "sub" in action or "aument" in action:
                cmd = "$wsh = New-Object -ComObject WScript.Shell; for($i=0;$i -lt 5;$i++){$wsh.SendKeys([char]175)}"
                subprocess.run(["powershell", "-Command", cmd], capture_output=True, timeout=3)
                return "Volumen del sistema aumentado."
            elif "baj" in action or "disminu" in action:
                cmd = "$wsh = New-Object -ComObject WScript.Shell; for($i=0;$i -lt 5;$i++){$wsh.SendKeys([char]174)}"
                subprocess.run(["powershell", "-Command", cmd], capture_output=True, timeout=3)
                return "Volumen del sistema disminuido."
            else:
                return "Comando de volumen no reconocido (prueba: 'silenciar volumen', 'subir volumen', 'bajar volumen')."
        except Exception as e:
            return f"No se pudo ajustar el volumen: {e}"

    clipboard_ring = clipboard_ring

    @staticmethod
    def get_active_window_info() -> Dict[str, str]:
        """
        Detecta en < 0.1ms la ventana activa y aplicación en primer plano en Windows usando ctypes.
        """
        friendly_names = {
            "code.exe": "Visual Studio Code",
            "chrome.exe": "Google Chrome",
            "msedge.exe": "Microsoft Edge",
            "firefox.exe": "Mozilla Firefox",
            "notepad.exe": "Bloc de Notas",
            "explorer.exe": "Explorador de Windows",
            "windowsterminal.exe": "Terminal de Windows",
            "powershell.exe": "PowerShell",
            "cmd.exe": "Símbolo del Sistema",
            "spotify.exe": "Spotify",
            "slack.exe": "Slack",
            "discord.exe": "Discord",
            "excel.exe": "Microsoft Excel",
            "winword.exe": "Microsoft Word",
            "powerpnt.exe": "Microsoft PowerPoint"
        }
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return {"title": "Escritorio de Windows", "process": "explorer.exe", "app_name": "Explorador de Windows"}
            length = user32.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            raw_title = buff.value.strip()

            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            proc_name = ""
            if pid.value:
                try:
                    proc = psutil.Process(pid.value)
                    proc_name = proc.name().lower()
                except Exception:
                    pass

            app_name = friendly_names.get(proc_name, proc_name.replace(".exe", "").title() if proc_name else "Ventana de Windows")
            title = raw_title or app_name
            return {
                "title": title,
                "process": proc_name,
                "app_name": app_name
            }
        except Exception as e:
            logger.debug(f"Error detectando ventana activa: {e}")
            return {"title": "Escritorio de Windows", "process": "explorer.exe", "app_name": "Explorador de Windows"}

    @staticmethod
    def generate_executive_briefing(user_name: str = "Fenix", salutation: str = "Comandante", task_manager=None) -> str:
        """
        Genera un briefing ejecutivo hablado y visual cruzando telemetría, tareas y contexto del día.
        """
        now = datetime.datetime.now()
        hour = now.hour
        if 5 <= hour < 12:
            greeting = f"¡Buenos días, {salutation} {user_name}!"
        elif 12 <= hour < 20:
            greeting = f"¡Buenas tardes, {salutation} {user_name}!"
        else:
            greeting = f"¡Buenas noches, {salutation} {user_name}!"

        # 1. Fecha y hora
        dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
        meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
        fecha_str = f"{dias[now.weekday()]} {now.day} de {meses[now.month - 1]}, {now.strftime('%H:%M')} hs"

        # 2. Salud del PC
        mem = psutil.virtual_memory()
        free_ram_gb = round(mem.available / (1024 ** 3), 1)
        cpu_pct = psutil.cpu_percent(interval=0.1)

        # 3. Ventana activa
        win = F3nixTools.get_active_window_info()
        win_info = f"Ubicación actual: {win['app_name']} ({win['title'][:35]}...)" if len(win['title']) > 35 else f"Ubicación: {win['app_name']}"

        # 4. Tareas del día
        task_str = "No tienes tareas pendientes anotadas."
        if task_manager:
            all_tasks = task_manager.get_all_tasks()
            pending = [t for t in all_tasks if not t.get("done", False)]
            if pending:
                top_task = pending[0].get("text", "")
                task_str = f"Tienes {len(pending)} tarea(s) pendiente(s). Prioridad #1: «{top_task}»."
            else:
                task_str = "¡Todas tus tareas están completadas al 100%!"

        briefing = (
            f"☀️ BRIEFING EJECUTIVO F3NIX\n"
            f"{greeting}\n"
            f"📅 {fecha_str}\n\n"
            f"💻 Telemetría de tu PC:\n"
            f"• RAM libre: {free_ram_gb} GB ({mem.percent}% en uso)\n"
            f"• CPU: {cpu_pct}%\n"
            f"• {win_info}\n\n"
            f"🎯 Tus Metas de Hoy:\n"
            f"• {task_str}\n\n"
            f"Sistemas en línea y listos para lo que ordenes."
        )
        return briefing

    @staticmethod
    def execute_routine(
        routine_name: str,
        user_name: str = "Fenix",
        timer_callback: Optional[Callable[[str], None]] = None,
        turbo_callback: Optional[Callable[[bool], None]] = None,
        task_manager=None
    ) -> str:
        """
        Ejecuta macros y rutinas operativas en un solo comando de voz.
        """
        r_lower = routine_name.lower()
        if any(w in r_lower for w in ["programacion", "programación", "desarrollo", "trabajo", "codigo", "código"]):
            F3nixTools.open_application("vscode")
            if turbo_callback:
                turbo_callback(True)
            if timer_callback:
                F3nixTools.start_timer(45.0, "Pomodoro de Programación (45m)", timer_callback)
            return (
                f"🚀 Modo Programación activado para {user_name}.\n"
                f"• Visual Studio Code iniciado.\n"
                f"• Pomodoro de 45 minutos en marcha.\n"
                f"• Modo Turbo ⚡ activado en la IA.\n"
                f"¡A construir código de alto nivel!"
            )

        elif any(w in r_lower for w in ["enfoque", "concentracion", "concentración", "estudio", "zen"]):
            F3nixTools.set_system_volume("bajar volumen")
            if timer_callback:
                F3nixTools.start_timer(25.0, "Sesión de Enfoque Profundo (25m)", timer_callback)
            return (
                f"🧘 Modo Enfoque activado.\n"
                f"• Volumen del sistema atenuado.\n"
                f"• Temporizador de 25 minutos de concentración iniciado.\n"
                f"Cero distracciones. Enfoque total en tu meta."
            )

        elif any(w in r_lower for w in ["cierra", "cierre", "cerrar", "fin de jornada", "terminar jornada", "descanso", "fin del dia", "fin del día"]):
            cleared = 0
            pending = 0
            if task_manager:
                cleared = task_manager.clear_completed()
                pending = task_manager.get_active_count()
            return (
                f"🌙 Jornada concluida con éxito, {user_name}.\n"
                f"• Tareas completadas archivadas: {cleared}.\n"
                f"• Tareas pendientes para mañana: {pending}.\n"
                f"¡Gran trabajo hoy! Descansa y recarga energías."
            )

        return f"Rutina '{routine_name}' no reconocida. Opciones disponibles: 'Modo programación', 'Modo enfoque' y 'Cierra mi jornada'."

    @staticmethod
    def play_sound_chime(mode: str = "start"):
        """
        Reproduce un suave efecto de sonido Hi-Tech (Jarvis style) de 20-45ms en segundo plano.
        - 'start': Tono ascendente al presionar F12 (micrófono abierto).
        - 'stop': Tono descendente al soltar F12 (procesando audio).
        - 'cancel': Tono corto de cancelación / Kill-Switch.
        """
        def _beep_worker():
            try:
                import winsound
                if mode == "start":
                    winsound.Beep(650, 35)
                    winsound.Beep(950, 45)
                elif mode == "stop":
                    winsound.Beep(850, 35)
                    winsound.Beep(550, 45)
                elif mode == "cancel":
                    winsound.Beep(450, 50)
            except Exception:
                pass

        threading.Thread(target=_beep_worker, daemon=True).start()
