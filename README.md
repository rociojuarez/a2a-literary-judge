# Sistema A2A - Análisis literario y ético multi-agente

Sistema multi-agente que utiliza el **protocolo A2A (Agent-to-Agent)** para analizar obras literarias desde una perspectiva ética y narrativa. Varios agentes especializados (Sacerdote, Crítico, Meta-crítico) detectan incoherencias y argumentan; un **Juez** orquesta el flujo y emite un veredicto final estructurado.

## Características

- **Protocolo A2A**: Agentes que se descubren y comunican mediante mensajes tipados (task_request, task_response, query, etc.).
- **Cuatro agentes especializados**:
  - **Sacerdote**: Detecta incoherencias morales y éticas en la obra.
  - **Crítico literario**: Detecta incoherencias narrativas y estructurales.
  - **Meta-crítico**: Contraargumenta y defiende las decisiones artísticas.
  - **Juez**: Coordina el análisis, recopila resultados y emite el veredicto final.
- **API REST** con FastAPI y documentación interactiva (`/docs`).
- **Interfaz web** para lanzar análisis y ver el flujo de mensajes en tiempo real.
- **WebSocket** para eventos en vivo (mensajes entre agentes).
- **Modo CLI** para ejecutar análisis sin levantar el servidor.

## Stack tecnológico

- **Python 3.9+**
- **LangChain / LangGraph** – orquestación de LLM y agentes
- **OpenAI** – modelo de lenguaje (configurable vía `OPENAI_MODEL`)
- **FastAPI + Uvicorn** – servidor HTTP y WebSocket
- **Pydantic** – modelos y validación

## Estructura del proyecto

```
.
├── main.py              # Punto de entrada (servidor o CLI)
├── requirements.txt
├── .env                 # Variables de entorno (no subir a Git)
├── agents/
│   ├── a2a_agents.py    # Implementación de los agentes A2A
│   ├── agent_cards.py   # Tarjetas de descubrimiento por agente
│   ├── models.py        # Modelos de mensajes, veredicto, etc.
│   ├── tools.py         # Herramientas/skills de los agentes
│   └── ...
├── server/
│   ├── app.py           # FastAPI: endpoints, WebSocket, UI estática
│   ├── message_bus.py   # Bus de mensajes entre agentes
│   └── discovery.py     # Servicio de descubrimiento A2A
└── static/
    └── index.html       # Interfaz web
```

## Requisitos previos

- Python 3.9 o superior
- Cuenta en OpenAI y API key

## Instalación

1. Clonar el repositorio (o descargar el proyecto):

   ```bash
   git clone https://github.com/TU_USUARIO/NOMBRE_REPO.git
   cd NOMBRE_REPO
   ```

2. Crear y activar un entorno virtual:

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Linux/macOS
   # .venv\Scripts\activate    # Windows
   ```

3. Instalar dependencias:

   ```bash
   pip install -r requirements.txt
   ```

4. Configurar variables de entorno:

   Crear un archivo `.env` en la raíz del proyecto:

   ```env
   OPENAI_API_KEY=tu_api_key_aqui
   OPENAI_MODEL=gpt-4o-mini
   BASE_URL=http://localhost:8000
   ```

   - `OPENAI_API_KEY` es obligatorio.
   - `OPENAI_MODEL` es opcional (por defecto `gpt-4o-mini`).
   - `BASE_URL` se usa para las URLs de discovery en las agent cards.

## Uso

### Servidor web (recomendado)

```bash
python main.py
```

- **Interfaz web**: http://localhost:8000/
- **Documentación API**: http://localhost:8000/docs
- **Discovery A2A**: http://localhost:8000/.well-known/agent.json
- **WebSocket**: ws://localhost:8000/ws

Desde la interfaz web puedes indicar título (y autor) del libro y lanzar el análisis; el veredicto y el flujo de mensajes se muestran en la misma página.

### Modo CLI (sin servidor)

```bash
python main.py --cli
```

Ejecuta un análisis de ejemplo (por defecto *Cadáver exquisito - Agustina Bazterrica*) y muestra el veredicto en JSON en la consola. Útil para pruebas rápidas.

### Ayuda

```bash
python main.py --help
```

## API principal

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Interfaz web estática |
| GET | `/.well-known/agent.json` | Discovery del sistema A2A |
| POST | `/analisis` | Ejecuta el análisis para un libro (body: `{"libro": "Título - Autor"}`) |
| GET | `/docs` | Documentación Swagger/OpenAPI |
| WebSocket | `/ws` | Eventos en tiempo real (mensajes entre agentes) |

El endpoint `/analisis` devuelve un objeto con las incoherencias detectadas, el veredicto del juez, nivel de controversia y recomendación de lectura.

## Licencia

Proyecto de uso educativo (ej. Henry). Ajusta la licencia según tu necesidad.
