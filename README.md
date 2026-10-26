# Proyecto F3nix 🚀
### Asistente de Escritorio IA con Avatar Flotante, Voz y Control por Teclado

**Proyecto F3nix** es una aplicación de escritorio open-source desarrollada para Windows 11 que actúa como un compañero de IA hiperinteligente y local (impulsado por Ollama). Cuenta con una interfaz gráfica flotante y transparente que se mantiene siempre por encima de tus aplicaciones (ideal para IDEs como VS Code o entornos de desarrollo), sistema de voz integrado de alta calidad y un sistema de control por voz mediante la tecla de acceso rápido **F12** (*Push-to-Talk*).

---

## 🌟 Características Principales

- **Interfaz Gráfica Flotante (HUD):** Una ventana sin bordes, transparente y siempre visible con avatar personalizado, halo reactivo animado (`idle`, `listening`, `thinking`, `speaking`, `alarm`), botón de ayuda rápida `[?]` y expansor a Studio `[⛶]`.
- **F3NIX Studio (Estilo Hermes Desktop):** Workspace de pantalla completa o ventana expandible con 4 áreas de trabajo:
  1. *Chat & Canvas:* Conversación enriquecida con burbujas visuales y selector de modelos.
  2. *Bóveda de Memoria (Vault):* Memoria persistente editable (`f3nix_memory.json`) con perfil de usuario, proyectos y hechos aprendidos.
  3. *Registro de Actividad en Vivo:* Cronología de acciones del agente (búsquedas web, visiones de pantalla, memoria, herramientas).
  4. *Visor de Documentos:* Carga y previsualización de archivos arrastrados para resúmenes y análisis instantáneos.
- **IA 100% Local y Privada:** Impulsado por **Ollama** ejecutando modelos como *Nous Hermes 3*, *Llama 3.1*, *Qwen 2.5 Coder*, *Phi-4*, garantizando total privacidad.
- **Tienda Visual de Cerebros:** Descarga nuevos modelos con barra de porcentaje en tiempo real sin tocar la consola.
- **Búsqueda Web en Vivo (DuckDuckGo):** Pregunta *"busca en internet..."* o *"noticias de..."* y F3NIX traerá información actualizada.
- **Lector Inteligente de Portapapeles & Drag & Drop:** Copia con `Ctrl+C` o arrastra archivos directamente al avatar flotante para analizarlos.
- **Dictado Mágico:** Di *"escribe: ... personaliza esta función"* y F3NIX escribirá directamente sobre la aplicación o editor donde tengas el cursor.
- **Temporizadores y Pomodoros:** Di *"avísame en 25 minutos"* y el sistema activará un temporizador visual y auditivo.
- **Sistema de Voz Ultra-Natural (TTS):** Generación de voz neural en español (`edge-tts`) con selector de voces (Álvaro, Jorge, Elvira, Dalia).
- **Modo "Pulsar para Hablar" (F12):** Audio en tiempo real mediante `F12` (*Push-to-Talk*), sin falsos disparos.

---

## 🛠️ Requisitos del Sistema

Antes de instalar el Proyecto F3nix, asegúrate de tener lo siguiente en tu PC con Windows 11:
1. **Python 3.10 o superior** instalado en el sistema.
2. **Ollama** instalado y ejecutándose en segundo plano (`https://ollama.com`).
3. Micrófono y altavoces activos.

---

## 📦 Guía de Instalación Rápida

1. Clona o descarga este repositorio:
```powershell
git clone https://github.com/TU_USUARIO/Proyecto-F3nix.git
cd Proyecto-F3nix
```

2. Instala las dependencias necesarias:
```powershell
pip install -r requirements.txt
```

3. Inicia la aplicación:
Haz doble clic en `run_f3nix.bat` o ejecuta:
```powershell
python thruster.py
```

*Si no tienes modelos descargados, F3NIX abrirá automáticamente la tienda gráfica de cerebros para que instales Nous Hermes 3 o Llama 3.1 con un solo clic.*

---

## 🎮 ¿Cómo se usa?

1. Al iniciar el script, verás el avatar flotando en la esquina inferior derecha de tu pantalla.
2. **Mantén presionada la tecla `F12`**, haz tu pregunta o da una instrucción por voz, y **suelta `F12`**.
3. Haz clic en **`[ ? ]`** para ver el acordeón interactivo de habilidades y ejemplos exactos de comandos.
4. Haz clic en **`[ ⛶ ]`** para abrir **F3NIX Studio** y acceder al canvas de chat, la bóveda de memoria persistente y el registro del agente.
5. Puedes soltar archivos sobre el avatar flotante en cualquier momento para analizarlos.

---

## 📂 Estructura del Proyecto

```text
Proyecto-F3nix/
│
├── thruster.py                 # Orquestador principal de F3NIX
├── config.json                 # Configuración de voz, modelos y accesos rápidos
├── f3nix_memory.json           # Bóveda de memoria permanente (Hermes Vault)
├── run_f3nix.bat               # Lanzador directo para Windows 11
├── Modelfile                   # Definición del system prompt y personalidad para Ollama
├── requirements.txt            # Dependencias de Python
│
├── core/
│   ├── ai_engine.py            # Motor Ollama, memoria persistente e inyección de contexto
│   ├── memory_vault.py         # Gestor de memoria a largo plazo (Hermes Vault)
│   ├── f3nix_tools.py          # Búsqueda web DuckDuckGo, telemetría, pomodoros y dictado
│   ├── voice_listener.py       # Escuchador Push-to-Talk (F12) con PyAudio y STT
│   └── voice_speaker.py        # Sintetizador de voz neural (TTS) con edge-tts y Pygame
│
└── ui/
    ├── floating_avatar.py      # HUD flotante transparente con halo reactivo y dropzone
    ├── f3nix_studio.py         # Workspace expandible estilo Hermes Desktop (4 pestañas)
    ├── command_deck.py         # Centro de comando rápido de habilidades
    ├── quick_guide_dialog.py   # Guía visual interactiva de superpoderes
    └── model_downloader_dialog.py # Tienda visual para descargar modelos de Ollama
```

---

## 🛠️ Contribuir

¡Las contribuciones son bienvenidas! Si deseas proponer nuevas herramientas o integraciones, siembra un *fork* del repositorio y abre un *Pull Request*.

---

**Desarrollado con dedicación por Fenix.**
