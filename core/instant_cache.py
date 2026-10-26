import time
import random
from typing import Optional, Tuple, Dict, Any

class InstantCache:
    """
    Motor de Caché Instantáneo (< 1ms) para Proyecto F3NIX.
    Evita encender inferencia de CPU pesada en Ollama para saludos habituales,
    agradecimientos, cortesías o consultas idénticas recientes.
    """
    _query_cache: Dict[str, Tuple[str, float]] = {}  # query -> (reply, timestamp)
    TTL_SECONDS = 300  # 5 minutos de validez para consultas idénticas
    MAX_CACHE_SIZE = 60

    @classmethod
    def get_instant_reply(cls, prompt: str, user_name: str = "Fenix", salutation: str = "Comandante") -> Optional[str]:
        p = prompt.strip().lower()
        if not p:
            return None

        # 1. Saludos rápidos
        greetings = [
            "hola", "buenas", "buen día", "buen dia", "buenos días", "buenos dias",
            "buenas tardes", "buenas noches", "qué tal", "que tal", "hola fenix", "hola f3nix"
        ]
        if p in greetings or (len(p) < 20 and any(p.startswith(g) for g in ["hola ", "buenas ", "buen día", "buenos días"])):
            replies = [
                f"¡Hola {salutation}! Sistemas en línea y listos. ¿En qué trabajamos hoy?",
                f"¡Buenas {salutation}! Motores al cien por ciento. ¿Qué necesitas?",
                f"¡Hola {user_name}! Todo listo y operativo. Dime qué hacemos.",
                f"¡Presente, {salutation}! Dime cuál es la misión de hoy."
            ]
            return random.choice(replies)

        # 2. Agradecimientos
        thanks = [
            "gracias", "muchas gracias", "muchísimas gracias", "muchisimas gracias",
            "mil gracias", "gracias fenix", "gracias f3nix", "genial gracias", "excelente gracias"
        ]
        if p in thanks:
            replies = [
                f"¡Con gusto, {salutation}! Aquí sigo listo para lo que necesites.",
                f"¡A tu servicio, {salutation}!",
                f"¡Un placer ayudarte, {user_name}! Siempre a la orden.",
                f"¡De nada {salutation}! Sigamos avanzando."
            ]
            return random.choice(replies)

        # 3. Estado de ánimo / Cómo estás
        status_inquiries = [
            "cómo estás", "como estas", "cómo te va", "como te va", "qué haces", "que haces",
            "cómo andas", "como andas", "todo bien", "todo bien?"
        ]
        if p in status_inquiries:
            replies = [
                f"¡Excelente, {salutation}! Todos los núcleos optimizados y la telemetría en verde. ¿Qué desafío tenemos?",
                f"¡Al cien por ciento y listo para la acción, {salutation}! ¿En qué te colaboro hoy?",
                f"¡Todo en orden y funcionando a máxima velocidad, {user_name}! ¿Qué planeas hacer?"
            ]
            return random.choice(replies)

        # 4. Despedidas
        farewells = [
            "adiós", "adios", "chau", "hasta luego", "nos vemos", "descansa",
            "buenas noches fenix", "buenas noches f3nix"
        ]
        if p in farewells:
            replies = [
                f"¡Hasta luego, {salutation}! Estaré en guardia cuando me llames con F12.",
                f"¡Nos vemos, {user_name}! Buen descanso y excelente jornada.",
                f"¡Entendido, {salutation}! Sistemas en reposo vigilante. Hasta pronto."
            ]
            return random.choice(replies)

        # 5. Identidad rápida
        identity = [
            "quién eres", "quien eres", "cómo te llamas", "como te llamas", "cuál es tu nombre", "cual es tu nombre"
        ]
        if p in identity:
            return f"Soy F3NIX, tu copiloto inteligente de escritorio para Windows 11, optimizado para asistirte con código, sistema y productividad."

        # 6. Caché dinámico de consultas idénticas recientes
        now = time.time()
        if p in cls._query_cache:
            cached_reply, timestamp = cls._query_cache[p]
            if now - timestamp < cls.TTL_SECONDS:
                return cached_reply
            else:
                del cls._query_cache[p]

        return None

    @classmethod
    def put_cache(cls, prompt: str, reply: str):
        """Guarda en caché respuestas para acelerar consultas repetidas."""
        p = prompt.strip().lower()
        if not p or len(p) > 200 or len(reply) > 2000:
            return

        # No cachear comandos dinámicos como hora, sistema, archivos o volumen
        dynamic_keywords = ["hora", "fecha", "sistema", "archivo", "volumen", "pantalla", "clima", "moneda", "precio"]
        if any(dk in p for dk in dynamic_keywords):
            return

        now = time.time()
        if len(cls._query_cache) >= cls.MAX_CACHE_SIZE:
            # Eliminar el más antiguo
            oldest_key = min(cls._query_cache.keys(), key=lambda k: cls._query_cache[k][1])
            del cls._query_cache[oldest_key]

        cls._query_cache[p] = (reply, now)
