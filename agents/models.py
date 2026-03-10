# agents/models.py
# ============================================================================
# MODELOS DE DATOS PARA EL SISTEMA A2A
# ============================================================================
# Este archivo define todos los modelos Pydantic que estructuran los datos
# que fluyen entre agentes. Pydantic nos da validación automática y
# serialización a JSON.
# ============================================================================

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime


# ============================================================================
# MODELOS ORIGINALES (para el análisis del libro)
# ============================================================================

class TipoIncoherencia(str, Enum):
    """Tipos de incoherencias detectables en el análisis literario."""
    MORAL = "moral"
    NARRATIVA = "narrativa"
    LOGICA = "logica"
    ETICA = "etica"
    ESTRUCTURAL = "estructural"


class IncoherenciaDetectada(BaseModel):
    """Una incoherencia encontrada en el libro."""
    tipo: TipoIncoherencia
    descripcion: str = Field(description="Descripción detallada de la incoherencia")
    contexto: str = Field(description="Contexto del libro donde ocurre")
    severidad: int = Field(ge=1, le=10, description="Gravedad de 1 a 10")
    quien_detecta: str = Field(description="Nombre del agente que la detectó")
    argumento: str = Field(description="Razonamiento del agente")


class VeredictoFinal(BaseModel):
    """Resultado final consolidado por el Juez."""
    libro: str = Field(default="Cadáver exquisito - Agustina Bazterrica")
    todas_las_incoherencias: List[IncoherenciaDetectada]
    veredicto_juez: str = Field(description="Conclusión razonada del juez")
    quien_tiene_razon: str = Field(description="sacerdote, critico, critico_del_critico, o empate")
    nivel_controversia: int = Field(ge=1, le=10, description="Qué tan polémico es el libro")
    recomendacion_lectura: str


# ============================================================================
# MODELOS A2A - AGENT CARD
# ============================================================================
# La Agent Card es el corazón del protocolo A2A. Es un documento JSON que
# describe completamente a un agente: qué hace, qué puede recibir, qué retorna.
# Otros agentes leen esta card para saber cómo comunicarse.
#
# Basado en el estándar de Google A2A:
# https://github.com/google/A2A
# ============================================================================

class AgentSkill(BaseModel):
    """
    Representa una habilidad/capacidad específica de un agente.

    Ejemplo: El agente Sacerdote tiene la skill "analisis_moral"
    que puede analizar aspectos morales de un texto.
    """
    id: str = Field(description="Identificador único de la skill")
    name: str = Field(description="Nombre legible de la skill")
    description: str = Field(description="Qué hace esta skill")
    input_schema: Optional[Dict[str, Any]] = Field(
        default=None,
        description="JSON Schema de los parámetros que acepta"
    )
    output_schema: Optional[Dict[str, Any]] = Field(
        default=None,
        description="JSON Schema de lo que retorna"
    )


class AgentCard(BaseModel):
    """
    Agent Card - Documento de identidad de un agente A2A.

    Esta es la pieza fundamental del protocolo A2A. Cada agente
    DEBE exponer su Agent Card en /.well-known/agent.json para
    que otros agentes puedan descubrirlo y saber cómo comunicarse.

    Campos principales:
    - name: Nombre del agente
    - description: Qué hace el agente
    - url: Endpoint base del agente
    - skills: Lista de habilidades que ofrece
    - protocol_version: Versión del protocolo A2A
    """
    name: str = Field(description="Nombre del agente")
    description: str = Field(description="Descripción de qué hace el agente")
    url: str = Field(description="URL base del agente (ej: http://localhost:8000/agent/sacerdote)")
    version: str = Field(default="1.0.0", description="Versión del agente")
    protocol_version: str = Field(default="0.1", description="Versión del protocolo A2A")
    skills: List[AgentSkill] = Field(default=[], description="Habilidades del agente")

    # Metadatos adicionales
    author: Optional[str] = Field(default=None, description="Autor del agente")
    documentation_url: Optional[str] = Field(default=None, description="URL de documentación")

    # Capacidades de comunicación
    capabilities: Dict[str, bool] = Field(
        default={
            "streaming": False,      # ¿Soporta respuestas en streaming?
            "push_notifications": False,  # ¿Puede enviar notificaciones?
            "state_transition_history": True  # ¿Guarda historial?
        },
        description="Capacidades técnicas del agente"
    )


# ============================================================================
# MODELOS A2A - MENSAJES ENTRE AGENTES
# ============================================================================
# Los agentes se comunican mediante mensajes estructurados.
# Cada mensaje tiene un tipo, un remitente, un destinatario, y contenido.
# ============================================================================

class MessageType(str, Enum):
    """Tipos de mensajes que pueden intercambiar los agentes."""

    # Mensajes de tarea
    TASK_REQUEST = "task_request"       # Solicitar que el agente haga algo
    TASK_RESPONSE = "task_response"     # Respuesta a una solicitud
    TASK_UPDATE = "task_update"         # Actualización de progreso

    # Mensajes de consulta
    QUERY = "query"                     # Pregunta a otro agente
    QUERY_RESPONSE = "query_response"   # Respuesta a una pregunta

    # Mensajes de sistema
    PING = "ping"                       # Verificar si el agente está activo
    PONG = "pong"                       # Respuesta al ping
    ERROR = "error"                     # Notificar un error

    # Mensajes de descubrimiento
    DISCOVER = "discover"               # Solicitar Agent Card
    AGENT_CARD = "agent_card"           # Responder con Agent Card


class A2AMessage(BaseModel):
    """
    Mensaje del protocolo A2A.

    Este es el formato estándar para TODA comunicación entre agentes.
    Incluye metadatos para tracking, routing y debugging.
    """
    # Identificación del mensaje
    id: str = Field(description="ID único del mensaje (UUID)")
    parent_id: Optional[str] = Field(
        default=None,
        description="ID del mensaje al que responde (para threading)"
    )
    conversation_id: str = Field(
        description="ID de la conversación/sesión completa"
    )

    # Routing
    from_agent: str = Field(description="Nombre del agente que envía")
    to_agent: str = Field(description="Nombre del agente destinatario")

    # Contenido
    type: MessageType = Field(description="Tipo de mensaje")
    content: Dict[str, Any] = Field(description="Contenido del mensaje")

    # Metadatos
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Cuándo se creó el mensaje"
    )
    metadata: Dict[str, Any] = Field(
        default={},
        description="Metadatos adicionales (para debugging, etc.)"
    )


class TaskRequest(BaseModel):
    """
    Solicitud de tarea para un agente.

    Cuando un agente quiere que otro haga algo, envía un TaskRequest
    dentro de un A2AMessage con type=TASK_REQUEST.
    """
    skill_id: str = Field(description="Qué skill del agente usar")
    input_data: Dict[str, Any] = Field(description="Parámetros para la skill")
    priority: int = Field(default=5, ge=1, le=10, description="Prioridad 1-10")
    timeout_seconds: Optional[int] = Field(
        default=120,
        description="Timeout máximo para la respuesta"
    )


class TaskResponse(BaseModel):
    """
    Respuesta a una solicitud de tarea.

    Cuando un agente completa una tarea, responde con TaskResponse
    dentro de un A2AMessage con type=TASK_RESPONSE.
    """
    success: bool = Field(description="¿La tarea se completó exitosamente?")
    result: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Resultado de la tarea (si fue exitosa)"
    )
    error: Optional[str] = Field(
        default=None,
        description="Mensaje de error (si falló)"
    )
    execution_time_ms: Optional[int] = Field(
        default=None,
        description="Tiempo de ejecución en milisegundos"
    )


# ============================================================================
# MODELOS A2A - REGISTRO DE AGENTES (para Discovery)
# ============================================================================

class AgentRegistration(BaseModel):
    """
    Registro de un agente en el servicio de descubrimiento.

    Cuando un agente se inicia, se registra con el Discovery Service
    para que otros agentes puedan encontrarlo.
    """
    agent_id: str = Field(description="ID único del agente")
    agent_card: AgentCard = Field(description="Agent Card del agente")
    status: str = Field(default="active", description="Estado: active, busy, offline")
    registered_at: datetime = Field(default_factory=datetime.now)
    last_heartbeat: datetime = Field(default_factory=datetime.now)


# ============================================================================
# MODELOS PARA LA INTERFAZ WEB (WebSocket)
# ============================================================================

class WebSocketEvent(BaseModel):
    """
    Evento enviado a la interfaz web via WebSocket.

    Cada vez que algo interesante pasa (un agente envía un mensaje,
    se descubre un agente, etc.), se envía este evento al frontend.
    """
    event_type: str = Field(description="Tipo de evento: message, discovery, status, etc.")
    timestamp: datetime = Field(default_factory=datetime.now)
    data: Dict[str, Any] = Field(description="Datos del evento")
