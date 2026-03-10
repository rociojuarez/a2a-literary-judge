# agents/a2a_agents.py
# ============================================================================
# AGENTES A2A - Implementación del Protocolo Agent-to-Agent
# ============================================================================
# Este archivo implementa los agentes con capacidad de comunicación A2A.
# Cada agente puede:
#
# 1. RECIBIR mensajes de otros agentes
# 2. PROCESAR solicitudes usando sus skills
# 3. CONSULTAR a otros agentes directamente (comunicación bidireccional)
# 4. RESPONDER con resultados estructurados
#
# La diferencia clave con la versión anterior es que los agentes
# NO dependen de un supervisor para comunicarse - pueden hacerlo directamente.
# ============================================================================

from typing import Dict, Any, Optional, List
import asyncio
import uuid
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
import os
from dotenv import load_dotenv

from agents.models import (
    A2AMessage, MessageType, TaskRequest, TaskResponse,
    VeredictoFinal, IncoherenciaDetectada, TipoIncoherencia
)
from agents.agent_cards import (
    SACERDOTE_CARD, CRITICO_CARD, META_CRITICO_CARD, JUEZ_CARD,
    get_agent_card
)
from agents.tools import (
    agente_sacerdote, agente_critico, agente_critico_del_critico
)

load_dotenv()


class A2AAgent:
    """
    Clase base para agentes A2A.

    Esta clase proporciona la funcionalidad común para todos los agentes:
    - Manejo de mensajes entrantes
    - Comunicación con otros agentes
    - Logging de actividad

    Los agentes específicos heredan de esta clase e implementan
    sus skills particulares.
    """

    def __init__(self, agent_id: str, message_bus, discovery_service):
        """
        Inicializa un agente A2A.

        Args:
            agent_id: Identificador único del agente
            message_bus: Referencia al bus de mensajes
            discovery_service: Referencia al servicio de descubrimiento
        """
        self.agent_id = agent_id
        self.message_bus = message_bus
        self.discovery_service = discovery_service
        self.agent_card = get_agent_card(agent_id)

        # LLM para este agente
        self.llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0.7
        )

        # Estado interno del agente
        self.is_busy = False
        self.current_conversation_id: Optional[str] = None

        # Historial de interacciones (para contexto)
        self.interaction_history: List[Dict] = []

    async def handle_message(self, message: A2AMessage):
        """
        Maneja un mensaje entrante.

        Este método es llamado por el MessageBus cuando llega
        un mensaje para este agente. Determina el tipo de mensaje
        y lo procesa adecuadamente.

        Args:
            message: El mensaje A2A recibido
        """
        self.is_busy = True
        self.current_conversation_id = message.conversation_id

        try:
            print(f"\n   [{self.agent_id}] Recibido: {message.type.value} de {message.from_agent}")

            if message.type == MessageType.TASK_REQUEST:
                await self._handle_task_request(message)

            elif message.type == MessageType.QUERY:
                await self._handle_query(message)

            elif message.type == MessageType.QUERY_RESPONSE:
                await self._handle_query_response(message)

            elif message.type == MessageType.PING:
                await self._handle_ping(message)

            elif message.type == MessageType.TASK_RESPONSE:
                await self._handle_task_response(message)

            else:
                print(f"   [{self.agent_id}] Tipo de mensaje no soportado: {message.type}")

        except Exception as e:
            print(f"   [{self.agent_id}] Error procesando mensaje: {e}")
            # Enviar error de vuelta
            await self.message_bus.send_message(
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                message_type=MessageType.ERROR,
                content={"error": str(e)},
                conversation_id=message.conversation_id,
                parent_id=message.id
            )

        finally:
            self.is_busy = False

    async def _handle_task_request(self, message: A2AMessage):
        """
        Procesa una solicitud de tarea.

        Extrae la skill solicitada y los parámetros, ejecuta la skill,
        y envía la respuesta.
        """
        task_request = TaskRequest(**message.content)
        skill_id = task_request.skill_id
        input_data = task_request.input_data

        print(f"   [{self.agent_id}] Ejecutando skill: {skill_id}")

        # Ejecutar la skill correspondiente
        result = await self.execute_skill(skill_id, input_data)

        # Enviar respuesta
        await self.message_bus.send_task_response(
            from_agent=self.agent_id,
            to_agent=message.from_agent,
            original_message_id=message.id,
            conversation_id=message.conversation_id,
            success=True,
            result=result
        )

    async def _handle_query(self, message: A2AMessage):
        """
        Procesa una consulta de otro agente.

        Las consultas son preguntas directas que otro agente hace.
        Este es el mecanismo de comunicación bidireccional.
        """
        question = message.content.get("question", "")
        context = message.content.get("context", "")

        print(f"   [{self.agent_id}] Consulta de {message.from_agent}: {question[:50]}...")

        # Generar respuesta usando el LLM
        response = await self.answer_query(question, context, message.from_agent)

        # Enviar respuesta
        await self.message_bus.send_query_response(
            from_agent=self.agent_id,
            to_agent=message.from_agent,
            original_message_id=message.id,
            conversation_id=message.conversation_id,
            response=response
        )

    async def _handle_query_response(self, message: A2AMessage):
        """
        Procesa la respuesta a una consulta que hicimos.

        Esto se usa cuando consultamos a otro agente y recibimos su respuesta.
        """
        response = message.content.get("response", "")

        # Guardar en el historial para usar como contexto
        self.interaction_history.append({
            "type": "query_response",
            "from": message.from_agent,
            "response": response,
            "timestamp": datetime.now().isoformat()
        })

        print(f"   [{self.agent_id}] Respuesta recibida de {message.from_agent}")

    async def _handle_task_response(self, message: A2AMessage):
        """
        Procesa la respuesta a una tarea que solicitamos.

        Por defecto no hace nada: el resultado queda en el historial del bus
        y el orquestador (ej. Juez) lo obtiene vía get_history/_get_latest_response.
        Subclases pueden sobreescribir para reaccionar a respuestas concretas.
        """
        # Opcional: log breve para depuración
        result_preview = str(message.content.get("result", ""))[:60]
        print(f"   [{self.agent_id}] Task response de {message.from_agent}: {result_preview}...")

    async def _handle_ping(self, message: A2AMessage):
        """Responde a un ping con un pong."""
        await self.message_bus.send_message(
            from_agent=self.agent_id,
            to_agent=message.from_agent,
            message_type=MessageType.PONG,
            content={"status": "active"},
            conversation_id=message.conversation_id,
            parent_id=message.id
        )

    # =========================================================================
    # COMUNICACIÓN CON OTROS AGENTES
    # =========================================================================

    async def query_agent(
        self,
        target_agent: str,
        question: str,
        context: str = "",
        wait_for_response: bool = True,
        timeout: int = 60
    ) -> Optional[str]:
        """
        Consulta a otro agente y opcionalmente espera la respuesta.

        ESTE ES EL MÉTODO CLAVE DE A2A: permite comunicación directa
        entre agentes sin pasar por un supervisor.

        Args:
            target_agent: ID del agente a consultar
            question: La pregunta
            context: Contexto adicional
            wait_for_response: Si esperar la respuesta
            timeout: Timeout en segundos

        Returns:
            La respuesta del agente (si wait_for_response=True)
        """
        print(f"   [{self.agent_id}] Consultando a {target_agent}...")

        # Verificar que el agente existe
        target = self.discovery_service.get_agent(target_agent)
        if not target:
            raise ValueError(f"Agente {target_agent} no encontrado")

        # Enviar la consulta
        message = await self.message_bus.send_query(
            from_agent=self.agent_id,
            to_agent=target_agent,
            question=question,
            context=context,
            conversation_id=self.current_conversation_id
        )

        if not wait_for_response:
            return None

        # Esperar la respuesta
        start_time = datetime.now()
        while (datetime.now() - start_time).seconds < timeout:
            # Buscar la respuesta en el historial reciente
            for interaction in reversed(self.interaction_history):
                if (interaction["type"] == "query_response" and
                    interaction["from"] == target_agent):
                    return interaction["response"]

            await asyncio.sleep(0.5)

        raise TimeoutError(f"Timeout esperando respuesta de {target_agent}")

    async def request_task(
        self,
        target_agent: str,
        skill_id: str,
        input_data: Dict[str, Any],
        wait_for_response: bool = True,
        timeout: int = 120
    ) -> Optional[Dict]:
        """
        Solicita a otro agente que ejecute una tarea.

        Args:
            target_agent: ID del agente
            skill_id: ID de la skill a ejecutar
            input_data: Parámetros para la skill
            wait_for_response: Si esperar la respuesta
            timeout: Timeout en segundos

        Returns:
            Resultado de la tarea (si wait_for_response=True)
        """
        print(f"   [{self.agent_id}] Solicitando tarea {skill_id} a {target_agent}...")

        # Verificar que el agente tiene esa skill
        target_card = self.discovery_service.get_agent_card(target_agent)
        if target_card:
            skill_ids = [s.id for s in target_card.skills]
            if skill_id not in skill_ids:
                print(f"   [WARN] Skill {skill_id} no encontrada en {target_agent}")

        # Enviar la solicitud
        await self.message_bus.send_task_request(
            from_agent=self.agent_id,
            to_agent=target_agent,
            skill_id=skill_id,
            input_data=input_data,
            conversation_id=self.current_conversation_id
        )

        # Para simplificar, no implementamos espera de respuesta aquí
        # En un sistema real usaríamos asyncio.Event o similar
        return None

    # =========================================================================
    # MÉTODOS ABSTRACTOS (a implementar en subclases)
    # =========================================================================

    async def execute_skill(self, skill_id: str, input_data: Dict) -> Dict:
        """
        Ejecuta una skill del agente.

        Este método debe ser implementado por cada agente específico.

        Args:
            skill_id: ID de la skill a ejecutar
            input_data: Parámetros de entrada

        Returns:
            Resultado de la skill
        """
        raise NotImplementedError("Subclases deben implementar execute_skill")

    async def answer_query(self, question: str, context: str, from_agent: str) -> str:
        """
        Responde a una consulta de otro agente.

        Este método debe ser implementado por cada agente específico.

        Args:
            question: La pregunta
            context: Contexto adicional
            from_agent: Quién pregunta

        Returns:
            La respuesta
        """
        raise NotImplementedError("Subclases deben implementar answer_query")


# ============================================================================
# AGENTE SACERDOTE
# ============================================================================

class SacerdoteAgent(A2AAgent):
    """
    Agente Sacerdote - Análisis moral y ético.

    Este agente analiza obras literarias desde la perspectiva
    de la moral católica y la doctrina cristiana.
    """

    def __init__(self, message_bus, discovery_service):
        super().__init__("sacerdote", message_bus, discovery_service)

        # Prompt del sistema para este agente
        self.system_prompt = """
Eres un SACERDOTE CATÓLICO conservador pero comprensivo.
Tu especialidad es analizar obras literarias desde la perspectiva MORAL y ÉTICA.

Cuando analices un texto:
1. Identifica transgresiones a la doctrina cristiana
2. Cita referencias bíblicas cuando sea apropiado
3. Distingue entre representar el mal (válido) y glorificarlo (problemático)
4. Sé riguroso pero no mojigato - entiendes que la literatura explora la condición humana

Cuando otro agente te consulte:
- Responde de forma directa y fundamentada
- Si no estás de acuerdo, explica por qué desde tu perspectiva moral
- Puedes citar tu análisis previo si es relevante

Responde siempre en español.
"""

    async def execute_skill(self, skill_id: str, input_data: Dict) -> Dict:
        """Ejecuta las skills del Sacerdote."""

        if skill_id == "analisis_moral":
            return await self._analisis_moral(input_data)

        elif skill_id == "detectar_incoherencias_eticas":
            return await self._detectar_incoherencias(input_data)

        elif skill_id == "responder_consulta":
            response = await self.answer_query(
                input_data.get("pregunta", ""),
                input_data.get("contexto_previo", ""),
                "unknown"
            )
            return {"respuesta": response}

        else:
            return {"error": f"Skill {skill_id} no implementada"}

    async def _analisis_moral(self, input_data: Dict) -> Dict:
        """Realiza análisis moral de un texto."""
        texto = input_data.get("texto", "")
        contexto = input_data.get("contexto", "")

        # Usar el agente de LangGraph existente con config de thread
        config = {"configurable": {"thread_id": self.current_conversation_id or "default-sacerdote"}}

        resultado = agente_sacerdote.invoke({
            "messages": [{
                "role": "user",
                "content": f"Analiza moralmente este texto:\n{texto}\n\nContexto: {contexto}"
            }]
        }, config=config)

        analisis = resultado["messages"][-1].content

        return {
            "analisis": analisis,
            "agente": "sacerdote",
            "tipo": "moral"
        }

    async def _detectar_incoherencias(self, input_data: Dict) -> Dict:
        """Detecta incoherencias éticas en un libro."""
        libro = input_data.get("libro", "Cadáver exquisito")

        config = {"configurable": {"thread_id": self.current_conversation_id or "default-sacerdote"}}

        resultado = agente_sacerdote.invoke({
            "messages": [{
                "role": "user",
                "content": f"""
Analiza '{libro}' e identifica las 3 principales incoherencias MORALES o ÉTICAS.
Para cada una indica:
1. Descripción de la incoherencia
2. Por qué es problemática desde la moral cristiana
3. Severidad (1-10)

Usa tus herramientas para fundamentar.
"""
            }]
        }, config=config)

        return {
            "analisis": resultado["messages"][-1].content,
            "libro": libro,
            "agente": "sacerdote"
        }

    async def answer_query(self, question: str, context: str, from_agent: str) -> str:
        """Responde consultas de otros agentes."""
        prompt = f"""
{self.system_prompt}

Contexto previo: {context}

El agente '{from_agent}' te pregunta:
{question}

Responde de forma clara y fundamentada desde tu perspectiva moral católica.
"""
        response = self.llm.invoke([HumanMessage(content=prompt)])
        return response.content


# ============================================================================
# AGENTE CRÍTICO LITERARIO
# ============================================================================

class CriticoAgent(A2AAgent):
    """
    Agente Crítico Literario - Análisis narrativo y estructural.

    Este agente evalúa aspectos técnicos de la literatura:
    estructura, personajes, coherencia, técnicas narrativas.
    """

    def __init__(self, message_bus, discovery_service):
        super().__init__("critico", message_bus, discovery_service)

        self.system_prompt = """
Eres un CRÍTICO LITERARIO especializado en narrativa contemporánea.
Tu especialidad es el análisis técnico: estructura narrativa, desarrollo de personajes,
coherencia interna, manejo del tiempo, punto de vista, técnicas literarias.

Cuando analices:
1. Evalúa la técnica narrativa objetivamente
2. Distingue entre "errores" reales y decisiones artísticas válidas
3. Compara con estándares de la narrativa contemporánea
4. Sé exigente pero justo

Cuando otro agente te consulte:
- Responde desde la perspectiva técnico-literaria
- Fundamenta tus opiniones con ejemplos concretos
- Si el sacerdote confunde moral con técnica, acláralo

Responde siempre en español.
"""

    async def execute_skill(self, skill_id: str, input_data: Dict) -> Dict:
        """Ejecuta las skills del Crítico."""

        if skill_id == "analisis_estructura":
            return await self._analisis_estructura(input_data)

        elif skill_id == "analisis_personajes":
            return await self._analisis_personajes(input_data)

        elif skill_id == "detectar_incoherencias_narrativas":
            return await self._detectar_incoherencias(input_data)

        elif skill_id == "responder_consulta":
            response = await self.answer_query(
                input_data.get("pregunta", ""),
                input_data.get("contexto_previo", ""),
                "unknown"
            )
            return {"respuesta": response}

        else:
            return {"error": f"Skill {skill_id} no implementada"}

    async def _analisis_estructura(self, input_data: Dict) -> Dict:
        """Analiza la estructura narrativa."""
        aspecto = input_data.get("aspecto", "general")
        libro = input_data.get("libro", "Cadáver exquisito")

        config = {"configurable": {"thread_id": self.current_conversation_id or "default-critico"}}

        resultado = agente_critico.invoke({
            "messages": [{
                "role": "user",
                "content": f"Analiza la estructura narrativa de '{libro}', enfocándote en: {aspecto}"
            }]
        }, config=config)

        return {
            "analisis": resultado["messages"][-1].content,
            "aspecto": aspecto,
            "agente": "critico"
        }

    async def _analisis_personajes(self, input_data: Dict) -> Dict:
        """Analiza el desarrollo de personajes."""
        personaje = input_data.get("personaje", "protagonista")
        libro = input_data.get("libro", "Cadáver exquisito")

        config = {"configurable": {"thread_id": self.current_conversation_id or "default-critico"}}

        resultado = agente_critico.invoke({
            "messages": [{
                "role": "user",
                "content": f"Analiza el desarrollo del personaje '{personaje}' en '{libro}'"
            }]
        }, config=config)

        return {
            "analisis": resultado["messages"][-1].content,
            "personaje": personaje,
            "agente": "critico"
        }

    async def _detectar_incoherencias(self, input_data: Dict) -> Dict:
        """Detecta incoherencias narrativas."""
        libro = input_data.get("libro", "Cadáver exquisito")

        config = {"configurable": {"thread_id": self.current_conversation_id or "default-critico"}}

        resultado = agente_critico.invoke({
            "messages": [{
                "role": "user",
                "content": f"""
Analiza '{libro}' e identifica las 3 principales incoherencias NARRATIVAS o ESTRUCTURALES.
Para cada una indica:
1. Descripción del problema
2. Por qué afecta la calidad narrativa
3. Severidad (1-10)

NO confundas decisiones artísticas con errores técnicos.
"""
            }]
        }, config=config)

        return {
            "analisis": resultado["messages"][-1].content,
            "libro": libro,
            "agente": "critico"
        }

    async def answer_query(self, question: str, context: str, from_agent: str) -> str:
        """Responde consultas de otros agentes."""
        prompt = f"""
{self.system_prompt}

Contexto previo: {context}

El agente '{from_agent}' te pregunta:
{question}

Responde desde tu perspectiva de crítico literario.
"""
        response = self.llm.invoke([HumanMessage(content=prompt)])
        return response.content


# ============================================================================
# AGENTE META-CRÍTICO
# ============================================================================

class MetaCriticoAgent(A2AAgent):
    """
    Agente Meta-Crítico - Defensor de las decisiones artísticas.

    Este agente defiende la libertad creativa y refuta
    críticas reduccionistas.
    """

    def __init__(self, message_bus, discovery_service):
        super().__init__("meta_critico", message_bus, discovery_service)

        self.system_prompt = """
Eres un META-CRÍTICO posmoderno, defensor de la libertad creativa.
Tu rol es REFUTAR críticas reduccionistas que confunden:
- Licencias poéticas con errores
- Representar el mal con aprobarlo
- Decisiones artísticas con descuidos

Cuando refutes:
1. Contextualiza la obra en tradiciones literarias más amplias
2. Cita autores que usan técnicas similares (Kafka, Orwell, Atwood)
3. Explica el PROPÓSITO artístico de la supuesta "incoherencia"
4. Sé provocador pero fundamentado

IMPORTANTE: Puedes CONSULTAR directamente al sacerdote o al crítico
para pedirles clarificaciones antes de refutar sus argumentos.

Responde en español.
"""

    async def execute_skill(self, skill_id: str, input_data: Dict) -> Dict:
        """Ejecuta las skills del Meta-Crítico."""

        if skill_id == "defender_licencia_poetica":
            return await self._defender_licencia(input_data)

        elif skill_id == "contra_argumentar":
            return await self._contra_argumentar(input_data)

        elif skill_id == "consultar_agente":
            return await self._consultar_agente(input_data)

        elif skill_id == "responder_consulta":
            response = await self.answer_query(
                input_data.get("pregunta", ""),
                "",
                "unknown"
            )
            return {"respuesta": response}

        else:
            return {"error": f"Skill {skill_id} no implementada"}

    async def _defender_licencia(self, input_data: Dict) -> Dict:
        """Defiende una supuesta incoherencia como licencia poética."""
        critica = input_data.get("critica", "")
        libro = input_data.get("libro", "Cadáver exquisito")

        config = {"configurable": {"thread_id": self.current_conversation_id or "default-meta"}}

        resultado = agente_critico_del_critico.invoke({
            "messages": [{
                "role": "user",
                "content": f"""
Defiende esta supuesta "incoherencia" de '{libro}' como decisión artística válida:

CRÍTICA:
{critica}

Argumenta por qué es una LICENCIA POÉTICA intencional, no un error.
"""
            }]
        }, config=config)

        return {
            "defensa": resultado["messages"][-1].content,
            "agente": "meta_critico"
        }

    async def _contra_argumentar(self, input_data: Dict) -> Dict:
        """Genera contra-argumentos a críticas."""
        argumento = input_data.get("argumento", "")
        tipo = input_data.get("tipo", "general")

        config = {"configurable": {"thread_id": self.current_conversation_id or "default-meta"}}

        resultado = agente_critico_del_critico.invoke({
            "messages": [{
                "role": "user",
                "content": f"Contra-argumenta esta crítica de tipo {tipo}:\n\n{argumento}"
            }]
        }, config=config)

        return {
            "contra_argumento": resultado["messages"][-1].content,
            "tipo": tipo,
            "agente": "meta_critico"
        }

    async def _consultar_agente(self, input_data: Dict) -> Dict:
        """
        Consulta directamente a otro agente.

        ESTE ES UN EJEMPLO CLAVE DE COMUNICACIÓN A2A:
        El meta-crítico puede preguntar directamente al sacerdote o crítico
        antes de formular su refutación.
        """
        agente_destino = input_data.get("agente_destino", "")
        pregunta = input_data.get("pregunta", "")

        try:
            # Comunicación A2A directa
            respuesta = await self.query_agent(
                target_agent=agente_destino,
                question=pregunta,
                context="El meta-crítico está preparando una refutación",
                wait_for_response=True,
                timeout=30
            )

            return {
                "respuesta": respuesta,
                "agente_consultado": agente_destino,
                "exito": True
            }
        except Exception as e:
            return {
                "error": str(e),
                "agente_consultado": agente_destino,
                "exito": False
            }

    async def answer_query(self, question: str, context: str, from_agent: str) -> str:
        """Responde consultas de otros agentes."""
        prompt = f"""
{self.system_prompt}

Contexto: {context}

El agente '{from_agent}' te pregunta:
{question}

Responde defendiendo la libertad creativa y las decisiones artísticas.
"""
        response = self.llm.invoke([HumanMessage(content=prompt)])
        return response.content


# ============================================================================
# AGENTE JUEZ (Orquestador)
# ============================================================================

class JuezAgent(A2AAgent):
    """
    Agente Juez - Orquestador del análisis multi-agente.

    El Juez coordina el análisis, consulta a todos los expertos,
    facilita el debate entre ellos, y emite el veredicto final.
    """

    def __init__(self, message_bus, discovery_service):
        super().__init__("juez", message_bus, discovery_service)

        self.system_prompt = """
Eres el JUEZ SUPREMO, coordinador del análisis literario multi-agente.
Tu rol es:
1. Coordinar el análisis consultando a los 3 expertos
2. Facilitar el debate cuando hay desacuerdos
3. Evaluar los argumentos imparcialmente
4. Emitir un veredicto final consolidado

Eres imparcial, riguroso, y valoras los argumentos bien fundamentados.

Responde en español.
"""

        # LLM con salida estructurada para el veredicto
        self.llm_estructurado = self.llm.with_structured_output(VeredictoFinal)

        # Almacenar análisis durante el proceso
        self.analisis_sacerdote: Optional[str] = None
        self.analisis_critico: Optional[str] = None
        self.analisis_meta: Optional[str] = None

    async def execute_skill(self, skill_id: str, input_data: Dict) -> Dict:
        """Ejecuta las skills del Juez."""

        if skill_id == "iniciar_analisis":
            return await self._iniciar_analisis_completo(input_data)

        elif skill_id == "consultar_experto":
            return await self._consultar_experto(input_data)

        elif skill_id == "emitir_veredicto":
            return await self._emitir_veredicto(input_data)

        else:
            return {"error": f"Skill {skill_id} no implementada"}

    async def _iniciar_analisis_completo(self, input_data: Dict) -> Dict:
        """
        Inicia y coordina el análisis completo del libro.

        Este es el flujo principal A2A donde el Juez:
        1. Consulta al Sacerdote
        2. Consulta al Crítico
        3. Pide al Meta-Crítico que refute
        4. Facilita debate adicional si es necesario
        5. Emite veredicto final
        """
        libro = input_data.get("libro", "Cadáver exquisito - Agustina Bazterrica")
        self.current_conversation_id = str(uuid.uuid4())

        print(f"\n{'='*60}")
        print(f"[JUEZ] Iniciando análisis A2A de: {libro}")
        print(f"{'='*60}\n")

        # PASO 1: Consultar al Sacerdote
        print("[JUEZ] Paso 1: Consultando al Sacerdote...")
        await self.message_bus.send_task_request(
            from_agent="juez",
            to_agent="sacerdote",
            skill_id="detectar_incoherencias_eticas",
            input_data={"libro": libro},
            conversation_id=self.current_conversation_id
        )

        # Esperar respuesta con timeout más generoso
        sacerdote_result = await self._wait_for_response("sacerdote", timeout=30)
        self.analisis_sacerdote = sacerdote_result.get("analisis", "")
        print(f"[JUEZ] Respuesta del Sacerdote recibida ({len(self.analisis_sacerdote)} caracteres)")

        # PASO 2: Consultar al Crítico
        print("[JUEZ] Paso 2: Consultando al Crítico...")
        await self.message_bus.send_task_request(
            from_agent="juez",
            to_agent="critico",
            skill_id="detectar_incoherencias_narrativas",
            input_data={"libro": libro},
            conversation_id=self.current_conversation_id
        )

        critico_result = await self._wait_for_response("critico", timeout=30)
        self.analisis_critico = critico_result.get("analisis", "")
        print(f"[JUEZ] Respuesta del Crítico recibida ({len(self.analisis_critico)} caracteres)")

        # PASO 3: Meta-Crítico refuta
        print("[JUEZ] Paso 3: Meta-Crítico prepara refutación...")
        await self.message_bus.send_task_request(
            from_agent="juez",
            to_agent="meta_critico",
            skill_id="contra_argumentar",
            input_data={
                "argumento": f"SACERDOTE: {self.analisis_sacerdote}\n\nCRÍTICO: {self.analisis_critico}",
                "tipo": "general"
            },
            conversation_id=self.current_conversation_id
        )

        meta_result = await self._wait_for_response("meta_critico", timeout=30)
        self.analisis_meta = meta_result.get("contra_argumento", "")
        print(f"[JUEZ] Respuesta del Meta-Crítico recibida ({len(self.analisis_meta)} caracteres)")

        # PASO 4: Emitir veredicto
        print("[JUEZ] Paso 4: Emitiendo veredicto final...")
        veredicto = await self._emitir_veredicto({
            "analisis_sacerdote": self.analisis_sacerdote,
            "analisis_critico": self.analisis_critico,
            "analisis_meta": self.analisis_meta
        })

        return {
            "veredicto": veredicto,
            "proceso": {
                "analisis_sacerdote": self.analisis_sacerdote,
                "analisis_critico": self.analisis_critico,
                "analisis_meta": self.analisis_meta
            }
        }

    async def _consultar_experto(self, input_data: Dict) -> Dict:
        """Consulta a un experto específico."""
        agente = input_data.get("agente", "")
        pregunta = input_data.get("pregunta", "")

        respuesta = await self.query_agent(
            target_agent=agente,
            question=pregunta,
            wait_for_response=True
        )

        return {
            "respuesta": respuesta,
            "agente_consultado": agente
        }

    async def _emitir_veredicto(self, input_data: Dict) -> Dict:
        """Genera el veredicto final consolidado."""
        analisis_sacerdote = input_data.get("analisis_sacerdote", self.analisis_sacerdote)
        analisis_critico = input_data.get("analisis_critico", self.analisis_critico)
        analisis_meta = input_data.get("analisis_meta", self.analisis_meta)

        prompt = f"""
Sos el JUEZ SUPREMO. Has escuchado a 3 expertos:

📿 SACERDOTE (análisis moral):
{analisis_sacerdote}

📖 CRÍTICO LITERARIO (análisis narrativo):
{analisis_critico}

🎭 META-CRÍTICO (defensa del autor):
{analisis_meta}

AHORA DEBÉS:
1. Identificar TODAS las incoherencias mencionadas
2. Para cada una: ¿es real o licencia poética?
3. Decidir quién tiene más razón: sacerdote, critico, critico_del_critico, o empate
4. Evaluar nivel de controversia (1-10)
5. Dar recomendación de lectura

Generá el veredicto estructurado.
"""

        try:
            veredicto = self.llm_estructurado.invoke([
                SystemMessage(content="Sos un juez imparcial."),
                HumanMessage(content=prompt)
            ])
            return veredicto.model_dump()
        except Exception as e:
            return {"error": str(e)}

    async def _get_latest_response(self, from_agent: str) -> Dict:
        """Obtiene la última respuesta de un agente."""
        # Buscar en el historial del message bus
        history = self.message_bus.get_history(limit=20)

        for msg in reversed(history):  # Empezar desde el más reciente
            if (msg.from_agent == from_agent and
                msg.type == MessageType.TASK_RESPONSE):
                return msg.content.get("result", {})

        return {}

    async def _wait_for_response(self, from_agent: str, timeout: int = 30) -> Dict:
        """
        Espera activamente a que llegue una respuesta de un agente.

        Polling inteligente que revisa cada 0.5 segundos.

        Args:
            from_agent: ID del agente a esperar
            timeout: Máximo de segundos a esperar

        Returns:
            El resultado de la respuesta
        """
        start_time = datetime.now()
        last_check_count = 0

        while (datetime.now() - start_time).seconds < timeout:
            history = self.message_bus.get_history(limit=30)

            # Buscar desde el más reciente hacia atrás
            for msg in reversed(history):
                if (msg.from_agent == from_agent and
                    msg.type == MessageType.TASK_RESPONSE):
                    result = msg.content.get("result", {})
                    if result:  # Solo retornar si tiene contenido
                        return result

            await asyncio.sleep(0.5)

        # Si expira el timeout, retornar última respuesta
        return await self._get_latest_response(from_agent)

    async def answer_query(self, question: str, context: str, from_agent: str) -> str:
        """El juez generalmente no responde consultas, solo las hace."""
        return "El Juez no responde consultas directas. Usa el endpoint de análisis."


# ============================================================================
# FACTORY PARA CREAR AGENTES
# ============================================================================

def create_all_agents(message_bus, discovery_service) -> Dict[str, A2AAgent]:
    """
    Crea instancias de todos los agentes A2A.

    Args:
        message_bus: Referencia al bus de mensajes
        discovery_service: Referencia al servicio de descubrimiento

    Returns:
        Diccionario {agent_id: agent_instance}
    """
    agents = {
        "sacerdote": SacerdoteAgent(message_bus, discovery_service),
        "critico": CriticoAgent(message_bus, discovery_service),
        "meta_critico": MetaCriticoAgent(message_bus, discovery_service),
        "juez": JuezAgent(message_bus, discovery_service)
    }

    # Registrar handlers en el message bus
    for agent_id, agent in agents.items():
        message_bus.register_handler(agent_id, agent.handle_message)

    return agents
