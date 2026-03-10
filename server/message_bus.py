# server/message_bus.py
# ============================================================================
# MESSAGE BUS - Sistema de Mensajería entre Agentes A2A
# ============================================================================
# El Message Bus es el canal de comunicación entre agentes.
# Implementa el patrón Pub/Sub para que los agentes puedan:
#
# 1. ENVIAR mensajes a otros agentes
# 2. RECIBIR mensajes dirigidos a ellos
# 3. BROADCAST a todos los agentes
#
# También mantiene un historial de mensajes para debugging
# y para que la UI web pueda mostrar la conversación en tiempo real.
# ============================================================================

from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
from collections import deque
import asyncio
import uuid

from agents.models import A2AMessage, MessageType, TaskRequest, TaskResponse


class MessageBus:
    """
    Bus de mensajes para comunicación A2A.

    Este componente es el corazón de la comunicación entre agentes.
    Todos los mensajes pasan por aquí, lo que permite:
    - Logging centralizado
    - Routing inteligente
    - Notificaciones a la UI
    - Historial de conversaciones

    Patrones implementados:
    - Message Bus / Event Bus
    - Publish-Subscribe
    - Observer (para notificaciones)
    """

    def __init__(self, max_history: int = 1000):
        # Cola de mensajes por agente: {agent_id: deque([messages])}
        self._queues: Dict[str, deque] = {}

        # Historial global de mensajes (para debugging y UI)
        self._history: deque = deque(maxlen=max_history)

        # Handlers registrados: {agent_id: handler_function}
        # Los handlers procesan mensajes cuando llegan
        self._handlers: Dict[str, Callable] = {}

        # Listeners para eventos (WebSocket, logging, etc.)
        self._listeners: List[Callable] = []

        # Conversaciones activas: {conversation_id: [message_ids]}
        self._conversations: Dict[str, List[str]] = {}

    # =========================================================================
    # ENVÍO DE MENSAJES
    # =========================================================================

    async def send_message(
        self,
        from_agent: str,
        to_agent: str,
        message_type: MessageType,
        content: Dict[str, Any],
        conversation_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> A2AMessage:
        """
        Envía un mensaje de un agente a otro.

        Este es el método principal de comunicación A2A.
        El mensaje se encola para el destinatario y se notifica a los listeners.

        Args:
            from_agent: ID del agente que envía
            to_agent: ID del agente destinatario
            message_type: Tipo de mensaje (TASK_REQUEST, QUERY, etc.)
            content: Contenido del mensaje
            conversation_id: ID de la conversación (se genera si no se provee)
            parent_id: ID del mensaje al que responde (para threading)
            metadata: Metadatos adicionales

        Returns:
            A2AMessage: El mensaje creado y enviado
        """
        # Generar IDs si no se proveen
        message_id = str(uuid.uuid4())
        if conversation_id is None:
            conversation_id = str(uuid.uuid4())

        # Crear el mensaje
        message = A2AMessage(
            id=message_id,
            parent_id=parent_id,
            conversation_id=conversation_id,
            from_agent=from_agent,
            to_agent=to_agent,
            type=message_type,
            content=content,
            timestamp=datetime.now(),
            metadata=metadata or {}
        )

        # Agregar al historial
        self._history.append(message)

        # Registrar en la conversación
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = []
        self._conversations[conversation_id].append(message_id)

        # Encolar para el destinatario
        if to_agent not in self._queues:
            self._queues[to_agent] = deque()
        self._queues[to_agent].append(message)

        # Notificar a los listeners (UI, logging, etc.)
        await self._notify_listeners("message_sent", message)

        # Log para debugging
        print(f"   [MessageBus] {from_agent} -> {to_agent}: {message_type.value}")

        # Si hay un handler registrado para el destinatario, procesarlo
        if to_agent in self._handlers:
            asyncio.create_task(self._process_message(message))

        return message

    async def _process_message(self, message: A2AMessage):
        """
        Procesa un mensaje llamando al handler del destinatario.

        Los handlers son funciones que los agentes registran para
        procesar mensajes entrantes.
        """
        handler = self._handlers.get(message.to_agent)
        if handler:
            try:
                await handler(message)
            except Exception as e:
                print(f"   [MessageBus] Error procesando mensaje: {e}")
                # Enviar mensaje de error de vuelta
                await self.send_message(
                    from_agent="system",
                    to_agent=message.from_agent,
                    message_type=MessageType.ERROR,
                    content={"error": str(e), "original_message_id": message.id},
                    conversation_id=message.conversation_id,
                    parent_id=message.id
                )

    # =========================================================================
    # MÉTODOS DE CONVENIENCIA PARA TIPOS DE MENSAJE
    # =========================================================================

    async def send_task_request(
        self,
        from_agent: str,
        to_agent: str,
        skill_id: str,
        input_data: Dict[str, Any],
        conversation_id: Optional[str] = None,
        priority: int = 5
    ) -> A2AMessage:
        """
        Envía una solicitud de tarea a un agente.

        Ejemplo: El Juez pide al Sacerdote que analice el libro.

        Args:
            from_agent: Agente que solicita
            to_agent: Agente que debe ejecutar
            skill_id: ID de la skill a usar
            input_data: Parámetros para la skill
            conversation_id: ID de conversación
            priority: Prioridad 1-10

        Returns:
            El mensaje enviado
        """
        task_request = TaskRequest(
            skill_id=skill_id,
            input_data=input_data,
            priority=priority
        )

        return await self.send_message(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=MessageType.TASK_REQUEST,
            content=task_request.model_dump(),
            conversation_id=conversation_id
        )

    async def send_task_response(
        self,
        from_agent: str,
        to_agent: str,
        original_message_id: str,
        conversation_id: str,
        success: bool,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> A2AMessage:
        """
        Envía la respuesta a una solicitud de tarea.

        Ejemplo: El Sacerdote responde al Juez con su análisis.

        Args:
            from_agent: Agente que responde
            to_agent: Agente que solicitó
            original_message_id: ID del mensaje original
            conversation_id: ID de conversación
            success: Si la tarea fue exitosa
            result: Resultado (si éxito)
            error: Error (si fallo)

        Returns:
            El mensaje enviado
        """
        task_response = TaskResponse(
            success=success,
            result=result,
            error=error
        )

        return await self.send_message(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=MessageType.TASK_RESPONSE,
            content=task_response.model_dump(),
            conversation_id=conversation_id,
            parent_id=original_message_id
        )

    async def send_query(
        self,
        from_agent: str,
        to_agent: str,
        question: str,
        context: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> A2AMessage:
        """
        Envía una consulta/pregunta a otro agente.

        Este es el mecanismo de comunicación BIDIRECCIONAL.
        Cualquier agente puede preguntar a cualquier otro.

        Ejemplo: El Meta-Crítico pregunta al Sacerdote
                 "¿Por qué consideras inmoral el capítulo 3?"

        Args:
            from_agent: Agente que pregunta
            to_agent: Agente que debe responder
            question: La pregunta
            context: Contexto adicional
            conversation_id: ID de conversación

        Returns:
            El mensaje enviado
        """
        return await self.send_message(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=MessageType.QUERY,
            content={
                "question": question,
                "context": context
            },
            conversation_id=conversation_id
        )

    async def send_query_response(
        self,
        from_agent: str,
        to_agent: str,
        original_message_id: str,
        conversation_id: str,
        response: str
    ) -> A2AMessage:
        """
        Responde a una consulta de otro agente.

        Args:
            from_agent: Agente que responde
            to_agent: Agente que preguntó
            original_message_id: ID de la pregunta original
            conversation_id: ID de conversación
            response: La respuesta

        Returns:
            El mensaje enviado
        """
        return await self.send_message(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=MessageType.QUERY_RESPONSE,
            content={"response": response},
            conversation_id=conversation_id,
            parent_id=original_message_id
        )

    # =========================================================================
    # RECEPCIÓN DE MENSAJES
    # =========================================================================

    def register_handler(self, agent_id: str, handler: Callable):
        """
        Registra un handler para procesar mensajes de un agente.

        El handler es una función async que recibe un A2AMessage
        y lo procesa (ejecuta la skill solicitada, responde, etc.)

        Args:
            agent_id: ID del agente
            handler: Función async (message: A2AMessage) -> None
        """
        self._handlers[agent_id] = handler
        print(f"   [MessageBus] Handler registrado para: {agent_id}")

    def unregister_handler(self, agent_id: str):
        """Elimina el handler de un agente."""
        if agent_id in self._handlers:
            del self._handlers[agent_id]

    def get_pending_messages(self, agent_id: str) -> List[A2AMessage]:
        """
        Obtiene los mensajes pendientes para un agente.

        Args:
            agent_id: ID del agente

        Returns:
            Lista de mensajes pendientes
        """
        if agent_id not in self._queues:
            return []
        messages = list(self._queues[agent_id])
        self._queues[agent_id].clear()
        return messages

    # =========================================================================
    # HISTORIAL Y CONVERSACIONES
    # =========================================================================

    def get_history(self, limit: int = 100) -> List[A2AMessage]:
        """
        Obtiene el historial de mensajes.

        Args:
            limit: Número máximo de mensajes

        Returns:
            Lista de mensajes (más recientes primero)
        """
        messages = list(self._history)
        messages.reverse()
        return messages[:limit]

    def get_conversation(self, conversation_id: str) -> List[A2AMessage]:
        """
        Obtiene todos los mensajes de una conversación.

        Args:
            conversation_id: ID de la conversación

        Returns:
            Lista de mensajes en orden cronológico
        """
        if conversation_id not in self._conversations:
            return []

        message_ids = self._conversations[conversation_id]
        messages = [m for m in self._history if m.id in message_ids]
        return sorted(messages, key=lambda m: m.timestamp)

    # =========================================================================
    # SISTEMA DE NOTIFICACIONES (para UI)
    # =========================================================================

    def add_listener(self, callback: Callable):
        """
        Agrega un listener para recibir notificaciones de mensajes.

        Los listeners reciben notificaciones cuando:
        - Se envía un mensaje
        - Se recibe una respuesta
        - Ocurre un error

        Esto se usa para actualizar la UI en tiempo real via WebSocket.

        Args:
            callback: Función async (event_type, message) -> None
        """
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable):
        """Elimina un listener."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    async def _notify_listeners(self, event_type: str, message: A2AMessage):
        """
        Notifica a todos los listeners de un evento.

        Args:
            event_type: Tipo de evento
            message: El mensaje relacionado
        """
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(event_type, message)
                else:
                    listener(event_type, message)
            except Exception as e:
                print(f"   [MessageBus] Error notificando listener: {e}")

    def clear_history(self):
        """Limpia todo el historial (útil para testing)."""
        self._history.clear()
        self._conversations.clear()
        self._queues.clear()


# ============================================================================
# INSTANCIA SINGLETON
# ============================================================================

message_bus = MessageBus()
