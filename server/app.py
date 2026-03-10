# server/app.py
# ============================================================================
# SERVIDOR FASTAPI PARA EL SISTEMA A2A
# ============================================================================
# Este es el servidor principal que expone:
#
# 1. ENDPOINTS DE DESCUBRIMIENTO (/.well-known/agent.json)
# 2. ENDPOINTS POR AGENTE (/agent/{nombre}/...)
# 3. WEBSOCKET para UI en tiempo real (/ws)
# 4. INTERFAZ WEB (/static/index.html)
#
# El servidor sigue el protocolo A2A de Google para que los agentes
# puedan descubrirse y comunicarse.
# ============================================================================

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Dict, List, Any, Optional
from datetime import datetime
import asyncio
import json
import os

from agents.models import A2AMessage, AgentCard, TaskRequest, WebSocketEvent
from agents.agent_cards import ALL_AGENT_CARDS, update_all_urls
from agents.a2a_agents import create_all_agents, A2AAgent

from server.discovery import discovery_service
from server.message_bus import message_bus


# ============================================================================
# CONFIGURACIÓN GLOBAL
# ============================================================================

# Almacén de agentes activos
agents: Dict[str, A2AAgent] = {}

# Conexiones WebSocket activas (para la UI)
websocket_connections: List[WebSocket] = []


# ============================================================================
# LIFECYCLE DEL SERVIDOR
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Maneja el ciclo de vida del servidor.

    Al iniciar:
    - Registra todos los agentes en el servicio de descubrimiento
    - Crea las instancias de los agentes A2A
    - Configura los listeners para WebSocket

    Al cerrar:
    - Limpia recursos
    """
    print("\n" + "=" * 60)
    print("🚀 INICIANDO SERVIDOR A2A")
    print("=" * 60 + "\n")

    # Actualizar URLs de las Agent Cards
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    update_all_urls(base_url)

    # Registrar agentes en el servicio de descubrimiento
    discovery_service.register_all_agents()

    # Crear instancias de los agentes
    global agents
    agents = create_all_agents(message_bus, discovery_service)
    print(f"[Server] {len(agents)} agentes A2A creados")

    # Configurar listener para enviar mensajes a WebSocket
    async def broadcast_message(event_type: str, message: A2AMessage):
        """Envía eventos a todos los WebSocket conectados."""
        if websocket_connections:
            event = WebSocketEvent(
                event_type=event_type,
                timestamp=datetime.now(),
                data={
                    "message_id": message.id,
                    "from_agent": message.from_agent,
                    "to_agent": message.to_agent,
                    "type": message.type.value,
                    "content": message.content,
                    "timestamp": message.timestamp.isoformat()
                }
            )
            event_json = event.model_dump_json()

            # Enviar a todos los WebSocket conectados
            for ws in websocket_connections.copy():
                try:
                    await ws.send_text(event_json)
                except:
                    websocket_connections.remove(ws)

    message_bus.add_listener(broadcast_message)

    print("[Server] Servidor listo!")
    print(f"[Server] UI disponible en: {base_url}/")
    print(f"[Server] Discovery en: {base_url}/.well-known/agent.json")
    print("=" * 60 + "\n")

    yield  # El servidor está corriendo

    # Cleanup al cerrar
    print("\n[Server] Cerrando servidor...")
    message_bus.clear_history()


# ============================================================================
# CREAR APP FASTAPI
# ============================================================================

app = FastAPI(
    title="Sistema A2A - Análisis Literario Multi-Agente",
    description="""
Sistema Agent-to-Agent (A2A) para análisis literario.

Implementa el protocolo A2A de Google para comunicación entre agentes autónomos.

## Agentes disponibles:
- **Sacerdote**: Análisis moral y ético
- **Crítico**: Análisis narrativo y estructural
- **Meta-Crítico**: Defensa de decisiones artísticas
- **Juez**: Coordinador y emisor del veredicto final

## Endpoints principales:
- `/.well-known/agent.json`: Documento de descubrimiento
- `/agent/{nombre}`: Endpoints específicos por agente
- `/analisis`: Iniciar análisis completo
- `/ws`: WebSocket para actualizaciones en tiempo real
    """,
    version="1.0.0",
    lifespan=lifespan
)

# CORS para permitir conexiones desde cualquier origen (desarrollo)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# ENDPOINTS DE DESCUBRIMIENTO (Protocolo A2A)
# ============================================================================

@app.get("/.well-known/agent.json", tags=["Discovery"])
async def get_discovery_document():
    """
    Documento de descubrimiento del servidor A2A.

    Este endpoint es FUNDAMENTAL en el protocolo A2A.
    Los clientes y otros servidores A2A lo consultan para
    conocer qué agentes están disponibles.

    Retorna:
        JSON con información de todos los agentes registrados
    """
    return discovery_service.get_discovery_document()


@app.get("/agents", tags=["Discovery"])
async def list_agents():
    """
    Lista todos los agentes registrados.

    Retorna información resumida de cada agente incluyendo
    su estado actual (active, busy, offline).
    """
    registrations = discovery_service.list_agents(only_active=True)
    return {
        "agents": [
            {
                "id": reg.agent_id,
                "name": reg.agent_card.name,
                "description": reg.agent_card.description,
                "status": reg.status,
                "url": reg.agent_card.url
            }
            for reg in registrations
        ]
    }


# ============================================================================
# ENDPOINTS POR AGENTE
# ============================================================================

@app.get("/agent/{agent_id}", tags=["Agents"])
async def get_agent_info(agent_id: str):
    """
    Obtiene información completa de un agente.

    Incluye su Agent Card con todas las skills disponibles.
    """
    card = discovery_service.get_agent_card(agent_id)
    if not card:
        raise HTTPException(status_code=404, detail=f"Agente '{agent_id}' no encontrado")

    return card.model_dump()


@app.get("/agent/{agent_id}/.well-known/agent.json", tags=["Agents"])
async def get_agent_card(agent_id: str):
    """
    Agent Card de un agente específico.

    Este es el endpoint estándar A2A para obtener la
    "tarjeta de identidad" de un agente.
    """
    card = discovery_service.get_agent_card(agent_id)
    if not card:
        raise HTTPException(status_code=404, detail=f"Agente '{agent_id}' no encontrado")

    return card.model_dump()


@app.post("/agent/{agent_id}/task", tags=["Agents"])
async def send_task_to_agent(agent_id: str, task: TaskRequest):
    """
    Envía una tarea a un agente específico.

    Este endpoint permite interactuar directamente con un agente,
    solicitando que ejecute una de sus skills.

    Args:
        agent_id: ID del agente
        task: Solicitud de tarea (skill_id, input_data, etc.)

    Returns:
        El resultado de la tarea
    """
    if agent_id not in agents:
        raise HTTPException(status_code=404, detail=f"Agente '{agent_id}' no encontrado")

    agent = agents[agent_id]

    # Ejecutar la skill
    result = await agent.execute_skill(task.skill_id, task.input_data)

    return {
        "agent_id": agent_id,
        "skill_id": task.skill_id,
        "result": result
    }


@app.post("/agent/{agent_id}/query", tags=["Agents"])
async def query_agent(agent_id: str, query: Dict[str, Any]):
    """
    Envía una consulta/pregunta a un agente.

    A diferencia de una tarea, una consulta es una pregunta
    abierta que el agente responde usando su conocimiento.
    """
    if agent_id not in agents:
        raise HTTPException(status_code=404, detail=f"Agente '{agent_id}' no encontrado")

    agent = agents[agent_id]
    question = query.get("question", "")
    context = query.get("context", "")

    response = await agent.answer_query(question, context, "api_client")

    return {
        "agent_id": agent_id,
        "question": question,
        "response": response
    }


# ============================================================================
# ENDPOINT DE ANÁLISIS COMPLETO
# ============================================================================

@app.post("/analisis", tags=["Análisis"])
async def iniciar_analisis(config: Optional[Dict[str, Any]] = None):
    """
    Inicia un análisis completo usando el sistema A2A.

    Este endpoint activa al Juez, quien coordina el análisis
    consultando a todos los agentes expertos.

    El proceso es:
    1. Juez consulta al Sacerdote (análisis moral)
    2. Juez consulta al Crítico (análisis narrativo)
    3. Meta-Crítico refuta las críticas
    4. Juez emite veredicto final

    Todos los mensajes se transmiten via WebSocket para
    visualización en tiempo real.

    Args:
        config: Configuración opcional
            - libro: Nombre del libro (default: "Cadáver exquisito")

    Returns:
        El veredicto final estructurado
    """
    import json

    libro = "Cadáver exquisito - Agustina Bazterrica"
    if config:
        libro = config.get("libro", libro)

    juez = agents.get("juez")
    if not juez:
        raise HTTPException(status_code=500, detail="Agente Juez no disponible")

    # Ejecutar análisis completo
    resultado = await juez.execute_skill("iniciar_analisis", {"libro": libro})

    # Mostrar resumen en consola
    if resultado and "veredicto" in resultado:
        veredicto = resultado["veredicto"]
        print("\n" + "=" * 70)
        print("✅ VEREDICTO FINAL (Consola)")
        print("=" * 70)
        print(json.dumps(
            veredicto if isinstance(veredicto, dict) else veredicto.model_dump(),
            indent=2,
            ensure_ascii=False,
            default=str
        ))
        print("=" * 70 + "\n")

    return resultado


@app.get("/analisis/historial", tags=["Análisis"])
async def get_historial():
    """
    Obtiene el historial de mensajes entre agentes.

    Útil para debugging y para ver el flujo de comunicación A2A.
    """
    history = message_bus.get_history(limit=50)
    return {
        "messages": [
            {
                "id": msg.id,
                "from": msg.from_agent,
                "to": msg.to_agent,
                "type": msg.type.value,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat()
            }
            for msg in history
        ]
    }


# ============================================================================
# WEBSOCKET PARA TIEMPO REAL
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket para recibir actualizaciones en tiempo real.

    La interfaz web se conecta aquí para ver los mensajes
    entre agentes mientras ocurren.

    Eventos enviados:
    - message_sent: Cuando un agente envía un mensaje
    - agent_registered: Cuando se registra un agente
    - agent_status_changed: Cuando cambia el estado de un agente
    """
    await websocket.accept()
    websocket_connections.append(websocket)

    print(f"[WebSocket] Nueva conexión. Total: {len(websocket_connections)}")

    # Enviar estado inicial
    await websocket.send_json({
        "event_type": "connected",
        "data": {
            "agents": [a.agent_id for a in discovery_service.list_agents()],
            "message": "Conectado al servidor A2A"
        }
    })

    try:
        while True:
            # Mantener conexión abierta
            data = await websocket.receive_text()

            # Procesar comandos del cliente (si los hay)
            try:
                cmd = json.loads(data)
                if cmd.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except Exception:
                pass

    except WebSocketDisconnect:
        pass  # Desconexión normal; limpieza en finally
    finally:
        if websocket in websocket_connections:
            websocket_connections.remove(websocket)
        print(f"[WebSocket] Conexión cerrada. Total: {len(websocket_connections)}")


# ============================================================================
# INTERFAZ WEB ESTÁTICA
# ============================================================================

# Montar archivos estáticos
static_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")


@app.get("/", response_class=HTMLResponse, tags=["UI"])
async def serve_ui():
    """
    Sirve la interfaz web principal.

    La interfaz muestra:
    - Agentes disponibles
    - Mensajes en tiempo real
    - Botón para iniciar análisis
    """
    index_path = os.path.join(static_path, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)

    # Si no existe el archivo, retornar HTML básico
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>A2A - Sistema Multi-Agente</title>
    </head>
    <body>
        <h1>Sistema A2A</h1>
        <p>Interfaz web no encontrada. Verifica que exista static/index.html</p>
        <p>Puedes usar los endpoints de la API directamente:</p>
        <ul>
            <li><a href="/.well-known/agent.json">Discovery</a></li>
            <li><a href="/agents">Lista de Agentes</a></li>
            <li><a href="/docs">Documentación API</a></li>
        </ul>
    </body>
    </html>
    """


# ============================================================================
# ENDPOINT DE HEALTH CHECK
# ============================================================================

@app.get("/health", tags=["System"])
async def health_check():
    """
    Verifica que el servidor esté funcionando.

    Útil para monitoring y load balancers.
    """
    return {
        "status": "healthy",
        "agents_count": len(agents),
        "websocket_connections": len(websocket_connections),
        "timestamp": datetime.now().isoformat()
    }
