import os
import re
import json
import time
import math
import logging
from typing import List, Dict, Any, Optional, Set, Callable

logger = logging.getLogger(__name__)

CACHE_FILE_PATH = "f3nix_rag_cache.json"

DEFAULT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css",
    ".json", ".md", ".txt", ".sql", ".c", ".cpp", ".h",
    ".cs", ".rs", ".go", ".bat", ".sh", ".yml", ".yaml", ".xml"
}

IGNORED_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "env", "dist", "build", ".idea", ".vscode", ".gemini",
    "brain", "site-packages", "obj", "bin"
}

SPANISH_STOP_WORDS = {
    "a", "al", "algo", "algunas", "algunos", "ante", "antes", "aqui", "aquí",
    "asi", "así", "bien", "bueno", "cada", "casi", "como", "cómo", "con", "contra",
    "cual", "cuál", "cuales", "cuáles", "cuando", "cuándo", "cuanto", "cuánto",
    "de", "del", "desde", "donde", "dónde", "dos", "el", "ella", "ellas", "ello",
    "ellos", "en", "era", "erais", "eran", "eras", "eres", "es", "esa", "esas",
    "ese", "eso", "esos", "esta", "está", "estaba", "estado", "estais", "estamos",
    "estan", "están", "estar", "estas", "estás", "este", "estos", "estoy", "fue",
    "ha", "habia", "había", "hace", "hacen", "hacer", "hacia", "hago", "hasta",
    "hay", "hola", "hoy", "la", "las", "le", "les", "lo", "los", "mas", "más",
    "me", "mi", "mí", "mia", "mía", "mias", "mías", "mio", "mío", "mios", "míos",
    "mis", "mucho", "muchos", "muy", "nada", "ni", "no", "nos", "nosotras",
    "nosotros", "nuestra", "nuestro", "otra", "otras", "otro", "otros", "para",
    "pero", "poco", "por", "porque", "por qué", "por que", "que", "qué", "quien",
    "quién", "quienes", "quiénes", "se", "sea", "sean", "ser", "si", "sí", "sido",
    "siempre", "siendo", "sin", "sobre", "sois", "solamente", "solo", "sólo", "son",
    "somos", "soy", "su", "sus", "suya", "suyo", "tal", "también", "tambien", "tanto",
    "te", "tenemos", "tener", "tenga", "tengo", "ti", "tiene", "tienen", "toda",
    "todas", "todo", "todos", "tu", "tú", "tus", "tuya", "tuyo", "un", "una",
    "unas", "uno", "unos", "va", "vamos", "van", "vaya", "verdad", "vosotras",
    "vosotros", "voy", "y", "ya", "yo"
}

class LocalRAG:
    """
    Motor RAG Local 100% privado y sin costo para indexar carpetas enteras
    de proyectos (código fuente y documentación) en el Proyecto F3nix.
    """
    def __init__(self, cache_file: str = CACHE_FILE_PATH):
        self.cache_file = cache_file
        self.folder_path: Optional[str] = None
        self.folder_name: str = ""
        self.files_count: int = 0
        self.chunks: List[Dict[str, Any]] = []
        self.inverted_index: Dict[str, List[int]] = {}
        self.idf: Dict[str, float] = {}
        self.last_indexed_at: str = ""
        self._load_cache()

    def has_index(self) -> bool:
        return bool(self.chunks and self.folder_path and os.path.exists(self.folder_path))

    @property
    def current_folder_name(self) -> str:
        return self.folder_name or (os.path.basename(self.folder_path) if self.folder_path else "Sin carpeta")

    def _tokenize(self, text: str) -> List[str]:
        """Extrae palabras clave normalizadas en minúsculas."""
        tokens = re.findall(r'[a-zA-Z0-9_\u00C0-\u017F]{2,}', text.lower())
        return tokens

    def index_directory(
        self,
        folder_path: str,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Escanea recursivamente la carpeta dada, fragmenta archivos de código y texto
        y construye el índice vectorial/léxico local.
        """
        abs_folder = os.path.abspath(folder_path)
        if not os.path.isdir(abs_folder):
            raise ValueError(f"El directorio '{abs_folder}' no existe.")

        self.folder_path = abs_folder
        self.folder_name = os.path.basename(abs_folder)
        all_files: List[str] = []

        # 1. Recolección de archivos válidos
        for root, dirs, files in os.walk(abs_folder):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in DEFAULT_EXTENSIONS:
                    all_files.append(os.path.join(root, f))

        self.files_count = len(all_files)
        new_chunks: List[Dict[str, Any]] = []
        chunk_id = 0

        # 2. Fragmentación inteligente con cálculo de líneas
        for idx, file_path in enumerate(all_files):
            if progress_callback:
                progress_callback(idx + 1, self.files_count, os.path.basename(file_path))

            try:
                # Saltar archivos gigantes (> 1 MB)
                if os.path.getsize(file_path) > 1024 * 1024:
                    continue

                rel_path = os.path.relpath(file_path, abs_folder).replace("\\", "/")
                with open(file_path, "r", encoding="utf-8", errors="ignore") as fp:
                    lines = fp.readlines()

                if not lines:
                    continue

                # Segmentación por bloques de líneas (~30 líneas o ~600 caracteres)
                step_lines = 25
                overlap = 6
                total_lines = len(lines)

                i = 0
                while i < total_lines:
                    chunk_slice = lines[i: i + step_lines]
                    chunk_text = "".join(chunk_slice).strip()

                    if len(chunk_text) > 20:
                        tokens = self._tokenize(chunk_text)
                        token_set = set(tokens)
                        new_chunks.append({
                            "id": chunk_id,
                            "rel_path": rel_path,
                            "start_line": i + 1,
                            "end_line": min(i + step_lines, total_lines),
                            "content": chunk_text,
                            "tokens": list(token_set)
                        })
                        chunk_id += 1

                    i += (step_lines - overlap)

            except Exception as e:
                logger.error(f"Error indexando {file_path}: {e}")

        self.chunks = new_chunks
        self.last_indexed_at = time.strftime("%Y-%m-%d %H:%M:%S")

        # 3. Construcción del índice inverso y pesos IDF
        self._build_index()
        self._save_cache()

        logger.info(f"RAG Indexado: {self.folder_name} -> {self.files_count} archivos, {len(self.chunks)} fragmentos.")
        return {
            "folder": self.folder_path,
            "folder_name": self.folder_name,
            "files": self.files_count,
            "chunks": len(self.chunks),
            "date": self.last_indexed_at
        }

    def _build_index(self):
        """Calcula el índice invertido y pesos IDF estilo BM25."""
        self.inverted_index = {}
        doc_count = len(self.chunks)
        if doc_count == 0:
            return

        for chunk in self.chunks:
            c_id = chunk["id"]
            for token in chunk["tokens"]:
                if token not in self.inverted_index:
                    self.inverted_index[token] = []
                self.inverted_index[token].append(c_id)

        self.idf = {}
        for token, posting in self.inverted_index.items():
            df = len(posting)
            self.idf[token] = math.log((doc_count - df + 0.5) / (df + 0.5) + 1.0)

    def query(self, search_query: str, top_k: int = 2, min_score: float = 3.0) -> List[Dict[str, Any]]:
        """
        Busca los fragmentos más relevantes de código o documentación
        filtrando palabras vacías y exigiendo una puntuación mínima de relevancia.
        """
        if not self.chunks or not search_query.strip():
            return []

        all_tokens = self._tokenize(search_query)
        # Filtrar palabras vacías (evita búsquedas espurias en saludos como 'hola como estas')
        query_tokens = [t for t in all_tokens if t not in SPANISH_STOP_WORDS and len(t) > 2]
        if not query_tokens:
            return []

        scores: Dict[int, float] = {}
        q_lower = search_query.lower()

        # Puntuación por coincidencia de términos ponderados por IDF
        for token in query_tokens:
            if token in self.inverted_index:
                weight = self.idf.get(token, 1.0)
                for chunk_id in self.inverted_index[token]:
                    scores[chunk_id] = scores.get(chunk_id, 0.0) + weight

        # Bonificación por coincidencia en nombre de archivo o ruta
        for c_id, score in list(scores.items()):
            chunk = self.chunks[c_id]
            rel_lower = chunk["rel_path"].lower()
            for token in query_tokens:
                if token in rel_lower:
                    scores[c_id] += 3.0
            # Bonificación si contiene la frase exacta
            if q_lower in chunk["content"].lower():
                scores[c_id] += 6.0

        # Filtrar fragmentos que no alcancen el umbral de relevancia
        valid_matches = [(cid, sc) for cid, sc in scores.items() if sc >= min_score]
        sorted_ids = sorted(valid_matches, key=lambda x: x[1], reverse=True)[:top_k]

        results = []
        for c_id, score in sorted_ids:
            chunk_data = dict(self.chunks[c_id])
            chunk_data["score"] = round(score, 2)
            results.append(chunk_data)

        return results

    def format_rag_context(self, search_query: str, top_k: int = 2) -> str:
        """
        Genera el bloque de contexto formateado y conciso para inyectar en el prompt.
        """
        matches = self.query(search_query, top_k=top_k)
        if not matches:
            return ""

        lines = [f"[BASE DE CONOCIMIENTO LOCAL (RAG - Carpeta: {self.current_folder_name})]:"]
        for m in matches:
            content_snippet = m['content'].strip()
            if len(content_snippet) > 600:
                content_snippet = content_snippet[:590] + "\n... [Fragmento acotado]"
            lines.append(
                f"\n--- Archivo: {m['rel_path']} (Líneas {m['start_line']}-{m['end_line']}) ---\n"
                f"{content_snippet}\n"
            )
        return "\n".join(lines)

    def _save_cache(self):
        try:
            data = {
                "folder_path": self.folder_path,
                "folder_name": self.folder_name,
                "files_count": self.files_count,
                "last_indexed_at": self.last_indexed_at,
                "chunks": self.chunks
            }
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error guardando caché RAG: {e}")

    def _load_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.folder_path = data.get("folder_path")
                self.folder_name = data.get("folder_name", "")
                self.files_count = data.get("files_count", 0)
                self.last_indexed_at = data.get("last_indexed_at", "")
                self.chunks = data.get("chunks", [])
                if self.chunks:
                    self._build_index()
                logger.info(f"Caché RAG cargado: {self.folder_name} ({len(self.chunks)} fragmentos)")
            except Exception as e:
                logger.error(f"Error cargando caché RAG: {e}")

    def clear_index(self):
        """Limpia el índice actual y remueve el archivo de caché."""
        self.folder_path = None
        self.folder_name = ""
        self.files_count = 0
        self.chunks = []
        self.inverted_index = {}
        self.idf = {}
        self.last_indexed_at = ""
        if os.path.exists(self.cache_file):
            try:
                os.remove(self.cache_file)
            except Exception:
                pass

    def get_stats(self) -> Dict[str, Any]:
        return {
            "has_index": self.has_index(),
            "folder_path": self.folder_path or "",
            "folder_name": self.current_folder_name,
            "files_count": self.files_count,
            "chunks_count": len(self.chunks),
            "last_indexed_at": self.last_indexed_at
        }
