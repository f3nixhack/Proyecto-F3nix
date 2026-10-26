"""
core/environment_doctor.py
Módulo de Diagnóstico y Auto-Reparación de Entorno para F3NIX.
Detecta si Ollama está apagado, no instalado, con rutas rotas o sin modelos,
y proporciona herramientas de auto-recuperación e instalación con un solo clic.
"""

import os
import sys
import time
import shutil
import logging
import subprocess
import requests
from typing import Optional, List, Dict, Tuple

logger = logging.getLogger("EnvironmentDoctor")

class EnvironmentDoctor:
    """Médico y reparador de dependencias y servicios locales de F3NIX."""

    @staticmethod
    def is_ollama_running(url: str = "http://localhost:11434") -> bool:
        """Verifica rápidamente si el servidor de Ollama responde."""
        try:
            r = requests.get(f"{url.rstrip('/')}/api/tags", timeout=1.2)
            return r.status_code == 200
        except Exception:
            return False

    @staticmethod
    def find_ollama_executable() -> Optional[str]:
        """Busca el ejecutable de Ollama en el sistema."""
        # 1. En PATH
        which_path = shutil.which("ollama")
        if which_path and os.path.exists(which_path):
            return which_path

        # 2. En LocalAppData (instalación estándar de Windows)
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if local_app_data:
            candidates = [
                os.path.join(local_app_data, "Programs", "Ollama", "ollama app.exe"),
                os.path.join(local_app_data, "Programs", "Ollama", "ollama.exe"),
            ]
            for c in candidates:
                if os.path.exists(c):
                    return c

        # 3. En Program Files
        for pf_var in ["ProgramFiles", "ProgramFiles(x86)"]:
            pf = os.environ.get(pf_var, "")
            if pf:
                candidate = os.path.join(pf, "Ollama", "ollama.exe")
                if os.path.exists(candidate):
                    return candidate

        return None

    @staticmethod
    def check_and_heal_ollama_path() -> Dict[str, any]:
        """
        Detecta y repara rutas rotas de modelos (por ejemplo, si OLLAMA_MODELS
        apunta a un disco externo 'D:' que fue desconectado).
        """
        healed = False
        reasons = []

        user_profile = os.environ.get("USERPROFILE", os.path.expanduser("~"))
        default_models_dir = os.path.join(user_profile, ".ollama", "models")

        # 1. Verificar variable de entorno OLLAMA_MODELS en el Registro de Windows
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
                try:
                    val, _ = winreg.QueryValueEx(key, "OLLAMA_MODELS")
                    if val:
                        # Si la ruta no existe o la unidad de disco no está montada
                        drive_letter = os.path.splitdrive(val)[0]
                        if (drive_letter and not os.path.exists(drive_letter + "\\")) or not os.path.exists(val):
                            logger.warning(f"Ruta OLLAMA_MODELS inválida en registro: '{val}'. Reparando...")
                            winreg.DeleteValue(key, "OLLAMA_MODELS")
                            os.environ.pop("OLLAMA_MODELS", None)
                            healed = True
                            reasons.append(f"Se eliminó la variable OLLAMA_MODELS que apuntaba al disco no existente '{val}'.")
                except FileNotFoundError:
                    pass  # No existe la variable en registro, lo cual es normal
        except Exception as e:
            logger.debug(f"Nota comprobando registro: {e}")

        # 2. Verificar si la variable en el proceso actual apunta a algo roto
        current_env = os.environ.get("OLLAMA_MODELS")
        if current_env:
            drive_letter = os.path.splitdrive(current_env)[0]
            if (drive_letter and not os.path.exists(drive_letter + "\\")) or not os.path.exists(current_env):
                os.environ.pop("OLLAMA_MODELS", None)
                healed = True
                reasons.append(f"Se restableció la variable de entorno local a la ruta por defecto.")

        # 3. Verificar si ~/.ollama/models es un enlace simbólico o unión huérfana
        if os.path.exists(default_models_dir):
            try:
                # Comprobar si es un reparse point roto
                os.listdir(default_models_dir)
            except (OSError, FileNotFoundError):
                # La unión apunta a un destino muerto
                try:
                    os.rmdir(default_models_dir)
                    os.makedirs(default_models_dir, exist_ok=True)
                    healed = True
                    reasons.append(f"Se eliminó una unión NTFS huérfana y se creó la carpeta limpia en '{default_models_dir}'.")
                except Exception as ex:
                    logger.error(f"Error reparando unión de modelos: {ex}")
        else:
            try:
                os.makedirs(default_models_dir, exist_ok=True)
            except Exception:
                pass

        return {
            "healed": healed,
            "reasons": reasons,
            "effective_models_dir": default_models_dir
        }

    @classmethod
    def auto_start_ollama(cls, wait_seconds: int = 8) -> Tuple[bool, str]:
        """
        Inicia el servicio Ollama en segundo plano y espera hasta que responda.
        Devuelve (True, "Mensaje de éxito") o (False, "Motivo del error").
        """
        if cls.is_ollama_running():
            return True, "Ollama ya se encuentra en ejecución."

        # Primero, asegurar que las rutas no estén rotas
        cls.check_and_heal_ollama_path()

        exe = cls.find_ollama_executable()
        if not exe:
            return False, "No se encontró el ejecutable de Ollama en tu computadora. Necesitas instalarlo."

        try:
            logger.info(f"Iniciando Ollama desde: {exe}")
            # En Windows usamos flags para desprender el proceso y evitar ventanas negras intrusivas
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            CREATE_NO_WINDOW = 0x08000000

            flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
            if "ollama app.exe" in exe.lower():
                subprocess.Popen([exe], creationflags=flags)
            else:
                flags |= CREATE_NO_WINDOW
                subprocess.Popen([exe, "serve"], creationflags=flags)

            # Esperar a que el servidor levante
            start_time = time.time()
            while time.time() - start_time < wait_seconds:
                time.sleep(0.5)
                if cls.is_ollama_running():
                    return True, "Ollama ha sido iniciado y está listo para responder."

            return False, f"Ollama fue lanzado pero no respondió en el puerto 11434 tras {wait_seconds} segundos."
        except Exception as e:
            return False, f"Error al intentar ejecutar Ollama: {e}"

    @classmethod
    def get_installed_models(cls, url: str = "http://localhost:11434") -> List[str]:
        """Obtiene la lista de nombres de modelos disponibles."""
        try:
            r = requests.get(f"{url.rstrip('/')}/api/tags", timeout=2.0)
            if r.status_code == 200:
                data = r.json()
                return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        except Exception:
            pass
        return []

    @staticmethod
    def get_disk_free_gb(path: Optional[str] = None) -> float:
        """Devuelve el espacio libre en Gigabytes del disco actual."""
        try:
            check_path = path or os.path.dirname(os.path.abspath(__file__))
            total, used, free = shutil.disk_usage(check_path)
            return round(free / (1024 ** 3), 1)
        except Exception:
            return 0.0

    @staticmethod
    def check_python_dependencies() -> Dict[str, bool]:
        """Comprueba que las dependencias críticas estén instaladas."""
        packages = {
            "PyQt6": "PyQt6",
            "requests": "requests",
            "edge_tts": "edge_tts",
            "pygame": "pygame",
            "speech_recognition": "speech_recognition",
            "keyboard": "keyboard",
            "pyaudio": "pyaudio"
        }
        results = {}
        for display_name, mod_name in packages.items():
            try:
                __import__(mod_name)
                results[display_name] = True
            except ImportError:
                results[display_name] = False
        return results

    @staticmethod
    def install_missing_packages(packages: List[str]) -> Tuple[bool, str]:
        """Instala automáticamente librerías faltantes mediante pip."""
        if not packages:
            return True, "No hay librerías pendientes de instalación."
        try:
            cmd = [sys.executable, "-m", "pip", "install"] + packages
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if res.returncode == 0:
                return True, f"Se instalaron correctamente: {', '.join(packages)}"
            else:
                return False, f"Error en pip: {res.stderr[:300]}"
        except Exception as e:
            return False, f"Fallo al invocar pip: {e}"

    @classmethod
    def get_full_diagnostics(cls) -> Dict[str, any]:
        """Realiza un chequeo exhaustivo del entorno y genera un reporte."""
        # 1. Chequeo y reparación preventiva de rutas
        heal_info = cls.check_and_heal_ollama_path()

        # 2. Estado de Ollama
        is_running = cls.is_ollama_running()
        ollama_exe = cls.find_ollama_executable()
        is_installed = (ollama_exe is not None)

        # 3. Modelos
        models = cls.get_installed_models() if is_running else []

        # 4. Espacio en disco
        free_gb = cls.get_disk_free_gb()

        # 5. Dependencias Python
        py_deps = cls.check_python_dependencies()
        all_deps_ok = all(py_deps.values())

        # Diagnóstico general
        all_green = (
            is_running and
            is_installed and
            len(models) > 0 and
            free_gb >= 3.0 and
            all_deps_ok
        )

        return {
            "all_green": all_green,
            "ollama_running": is_running,
            "ollama_installed": is_installed,
            "ollama_path": ollama_exe,
            "models": models,
            "models_count": len(models),
            "free_disk_gb": free_gb,
            "python_dependencies": py_deps,
            "python_all_ok": all_deps_ok,
            "healed_paths": heal_info["healed"],
            "heal_reasons": heal_info["reasons"],
            "models_dir": heal_info["effective_models_dir"]
        }
