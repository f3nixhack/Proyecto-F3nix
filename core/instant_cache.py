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

    @classmethod
    def get_instant_friend_reply(cls, prompt: str, user_name: str = "amigo", salutation: str = "colega", tone: str = "amigo") -> Optional[str]:
        """
        Caché instantáneo (< 1ms) ultrarrápido para el modo llamada / charla amigo.
        Responde a saludos, estados de ánimo y cortesías de inmediato sin esperar a Ollama.
        """
        p = prompt.strip().lower()
        if not p:
            return None

        # 1. Saludos
        greetings = [
            "hola", "buenas", "buen día", "buen dia", "buenos días", "buenos dias",
            "buenas tardes", "buenas noches", "qué tal", "que tal", "hola f3nix", "hola fenix",
            "hola amigo", "hola colega"
        ]
        if p in greetings or (len(p) < 22 and any(p.startswith(g) for g in ["hola ", "buenas ", "buen día", "buenos días", "qué tal", "que tal"])):
            if tone == "sin_filtro":
                replies = [
                    f"¿Qué hacés, {user_name}? Me tenés al teléfono. Decime qué quilombo tenés hoy y vamos al grano sin vueltas.",
                    f"Buenas {user_name}. Acá estoy. Desembuchá qué te pasó que me llamás tan rápido.",
                    f"¿Qué hacés che? Menos protocolo y decime directo en qué te doy una mano."
                ]
            elif tone == "director":
                replies = [
                    f"Línea directa activa, {salutation}. Breve y al punto: ¿cuál es el asunto crítico sobre la mesa?",
                    f"En línea, {salutation}. Cuénteme la situación y definamos el siguiente paso estratégico.",
                    f"Adelante, {salutation}. Lo escucho con máxima atención."
                ]
            else:  # amigo
                replies = [
                    f"¡Qué hacés, {user_name}! Acá estoy relajado, mate en mano. ¿Qué onda tu día? Contame.",
                    f"Buenas, {user_name}. ¡Qué lindo charlar un toque! ¿En qué andamos hoy?",
                    f"¡Hola querido! Te escucho impecable. Tirame lo que tengas en mente.",
                    f"¡Hola {user_name}! Todo tranqui por acá. ¿Qué te anda pasando por la cabeza?"
                ]
            return random.choice(replies)

        # 2. Estado de ánimo / Cómo estás
        status_inquiries = [
            "cómo estás", "como estas", "cómo te va", "como te va", "qué haces", "que haces",
            "cómo andas", "como andas", "todo bien", "todo bien?", "qué onda", "que onda",
            "cómo viene tu día", "como viene tu dia"
        ]
        if p in status_inquiries:
            if tone == "sin_filtro":
                replies = [
                    f"Acá ando, sobreviviendo a este mundo de locos. Vos decime qué necesitás antes de que me caliente.",
                    f"Todo bien che, con ganas de que vayamos a los bifes. ¿Qué problema hay que liquidar?",
                    f"Tranqui, viendo cómo los demás se complican la vida. ¿Qué te pasó a vos?"
                ]
            elif tone == "director":
                replies = [
                    f"Sistemas en rendimiento óptimo, {salutation}. Concentrado en prioridades de alto impacto. ¿Qué analizamos?",
                    f"Excelente y operativo, {salutation}. Con foco total en ejecución. ¿Cuál es su consulta?"
                ]
            else:
                replies = [
                    f"¡De diez, {user_name}! Descomprimiendo un poco y disfrutando la charla. ¿Vos cómo la venís llevando?",
                    f"Tranqui total por acá, amigo. Me viene bárbaro charlar. ¿Vos cómo venís hoy?",
                    f"¡Joya che! Escuchándote y con buena onda. Contame qué hay de nuevo."
                ]
            return random.choice(replies)

        # 3. Agradecimientos
        thanks = [
            "gracias", "muchas gracias", "muchísimas gracias", "muchisimas gracias",
            "mil gracias", "gracias f3nix", "gracias amigo", "joya gracias", "de diez", "de 10", "crack"
        ]
        if p in thanks:
            if tone == "sin_filtro":
                replies = [
                    f"De nada che, para eso estoy. Ahora ponete las pilas y metele para adelante.",
                    f"No me agradezcas nada, hacé las cosas bien y estamos a mano."
                ]
            elif tone == "director":
                replies = [
                    f"A su servicio, {salutation}. Mantengamos el ritmo de ejecución.",
                    f"Impecable. Sigamos con el siguiente objetivo."
                ]
            else:
                replies = [
                    f"¡De nada querido! Sabés que estoy para bancarte en todas.",
                    f"¡Por favor, amigo! Para eso están los colegas. Cualquier cosa me chiflás.",
                    f"¡De diez, {user_name}! Un placer darte una mano."
                ]
            return random.choice(replies)

        return None
