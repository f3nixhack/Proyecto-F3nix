import os
import time
import subprocess
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

IGNORED_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "build", ".dart_tool", "dist", ".idea", ".vscode", "appdata",
    "windows", "program files", "program files (x86)", "$recycle.bin",
    "system volume information", ".gradle", "site-packages"
}

class FileSearcher:
    """
    Buscador rápido de archivos y proyectos locales en Windows 11 para el Proyecto F3NIX.
    Escanea rutas prioritarias (D:\\, Escritorio, Documentos, Descargas).
    Incluye caché en memoria para responder en 0.01 segundos ante búsquedas sucesivas.
    """
    _search_cache: Dict[str, Any] = {}
    CACHE_TTL_SECONDS = 180

    def __init__(self, search_roots: Optional[List[str]] = None):
        if search_roots is None:
            user_home = os.path.expanduser("~")
            roots = []
            # Rutas de usuario
            desktop = os.path.join(user_home, "Desktop")
            onedrive_desktop = os.path.join(user_home, "OneDrive", "Desktop")
            docs = os.path.join(user_home, "Documents")
            onedrive_docs = os.path.join(user_home, "OneDrive", "Documentos")
            downloads = os.path.join(user_home, "Downloads")

            for r in [onedrive_desktop, desktop, onedrive_docs, docs, downloads]:
                if os.path.exists(r) and r not in roots:
                    roots.append(r)

            # Disco D: (proyectos y almacenamiento principal)
            if os.path.exists("D:\\"):
                roots.append("D:\\")
            elif os.path.exists("d:\\"):
                roots.append("d:\\")

            self.search_roots = roots
        else:
            self.search_roots = search_roots

    def search(self, query: str, max_results: int = 4, max_depth: int = 4) -> List[Dict[str, Any]]:
        """
        Busca archivos o carpetas que coincidan con la consulta.
        Retorna una lista de diccionarios con metadatos del archivo.
        """
        clean_q = query.strip().lower()
        if not clean_q:
            return []

        now = time.time()
        cache_key = f"{clean_q}_{max_results}_{max_depth}"
        if cache_key in self._search_cache:
            cached_results, timestamp = self._search_cache[cache_key]
            if now - timestamp < self.CACHE_TTL_SECONDS:
                logger.debug(f"Retornando resultados de búsqueda en caché para: {clean_q}")
                return cached_results

        results = []
        seen_paths = set()

        for root_dir in self.search_roots:
            if not os.path.exists(root_dir):
                continue

            root_depth = root_dir.rstrip(os.sep).count(os.sep)

            for current_root, dirs, files in os.walk(root_dir):
                # Filtrar carpetas ignoradas
                dirs[:] = [d for d in dirs if d.lower() not in IGNORED_DIRS and not d.startswith(".")]

                # Limitar profundidad para que sea ágil
                cur_depth = current_root.rstrip(os.sep).count(os.sep)
                if cur_depth - root_depth > max_depth:
                    dirs.clear()
                    continue

                # 1. Chequeo de nombres de archivos
                for f in files:
                    f_lower = f.lower()
                    if clean_q in f_lower:
                        full_path = os.path.join(current_root, f)
                        if full_path in seen_paths:
                            continue
                        seen_paths.add(full_path)

                        try:
                            stat = os.stat(full_path)
                            size_kb = round(stat.st_size / 1024, 1)
                            mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y %H:%M")
                            score = 10 if f_lower == clean_q else (5 if f_lower.startswith(clean_q) else 2)
                            results.append({
                                "name": f,
                                "path": full_path,
                                "size_kb": size_kb,
                                "modified": mtime,
                                "is_dir": False,
                                "score": score,
                                "mtime_raw": stat.st_mtime
                            })
                        except Exception:
                            pass

                # 2. Chequeo de nombres de carpetas
                for d in dirs:
                    d_lower = d.lower()
                    if clean_q in d_lower:
                        full_path = os.path.join(current_root, d)
                        if full_path in seen_paths:
                            continue
                        seen_paths.add(full_path)
                        try:
                            stat = os.stat(full_path)
                            mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y %H:%M")
                            score = 8 if d_lower == clean_q else 3
                            results.append({
                                "name": f"📁 {d}",
                                "path": full_path,
                                "size_kb": 0,
                                "modified": mtime,
                                "is_dir": True,
                                "score": score,
                                "mtime_raw": stat.st_mtime
                            })
                        except Exception:
                            pass

        # Ordenar por score de coincidencia y luego por fecha de modificación reciente
        results.sort(key=lambda x: (x["score"], x["mtime_raw"]), reverse=True)
        final_results = results[:max_results]
        self._search_cache[cache_key] = (final_results, now)
        return final_results

    @staticmethod
    def open_file(path: str) -> bool:
        """Abre el archivo con su aplicación predeterminada de Windows."""
        try:
            if os.path.exists(path):
                os.startfile(path)
                return True
        except Exception as e:
            logger.error(f"Error abriendo archivo {path}: {e}")
        return False

    @staticmethod
    def reveal_in_explorer(path: str) -> bool:
        """Abre el Explorador de Windows seleccionando el archivo o carpeta."""
        try:
            if os.path.exists(path):
                norm = os.path.normpath(path)
                subprocess.Popen(f'explorer.exe /select,"{norm}"')
                return True
        except Exception as e:
            logger.error(f"Error revelando archivo en explorador {path}: {e}")
        return False
