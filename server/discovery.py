# server/discovery.py
# ============================================================================
# SERVICIO DE DESCUBRIMIENTO DE AGENTES (Discovery Service)
# ============================================================================
# Este servicio es fundamental en el protocolo A2A. Permite que los agentes:
#
# 1. REGISTRARSE: Cuando un agente inicia, se registra aquí
# 2. DESCUBRIRSE: Los agentes pueden buscar otros agentes por nombre o skill
# 3. HEARTBEAT: Verificar que los agentes siguen activos
#
# En un sistema distribuido real, esto sería un servicio separado.
# Aquí lo implementamos como un singleton dentro del servidor.
# ============================================================================

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from agents.models import AgentCard, AgentRegistration
from agents.agent_cards import ALL_AGENT_CARDS
import asyncio


class DiscoveryService:
    """
    Servicio de descubrimiento de agentes A2A.

    Este servicio mantiene un registro de todos los agentes activos
    y permite que se descubran mutuamente.

    Patrones implementados:
    - Service Registry: Registro centralizado de agentes
    - Health Check: Verificación de agentes activos
    - Service Discovery: Búsqueda de agentes por capacidades
    """

    def __init__(self):
        # Registro de agentes: {agent_id: AgentRegistration}
        self._registry: Dict[str, AgentRegistration] = {}

        # Timeout para considerar un agente como inactivo (segundos)
        self._heartbeat_timeout = 60

        # Lista de listeners para notificar cambios (patrón Observer)
        self._listeners: List[callable] = []

    # =========================================================================
    # REGISTRO DE AGENTES
    # =========================================================================

    def register_agent(self, agent_card: AgentCard) -> AgentRegistration:
        """
        Registra un nuevo agente en el servicio de descubrimiento.

        Esto se llama cuando un agente "se levanta" y quiere ser visible
        para otros agentes del sistema.

        Args:
            agent_card: La Agent Card del agente

        Returns:
            AgentRegistration: El registro creado
        """
        registration = AgentRegistration(
            agent_id=agent_card.name,
            agent_card=agent_card,
            status="active",
            registered_at=datetime.now(),
            last_heartbeat=datetime.now()
        )

        self._registry[agent_card.name] = registration

        # Notificar a los listeners (para la UI web)
        self._notify_listeners("agent_registered", {
            "agent_id": agent_card.name,
            "agent_card": agent_card.model_dump()
        })

        print(f"   [Discovery] Agente registrado: {agent_card.name}")

        return registration

    def unregister_agent(self, agent_id: str) -> bool:
        """
        Elimina un agente del registro.

        Se llama cuando un agente se apaga de forma controlada.

        Args:
            agent_id: ID del agente a eliminar

        Returns:
            bool: True si se eliminó, False si no existía
        """
        if agent_id in self._registry:
            del self._registry[agent_id]
            self._notify_listeners("agent_unregistered", {"agent_id": agent_id})
            print(f"   [Discovery] Agente eliminado: {agent_id}")
            return True
        return False

    def update_heartbeat(self, agent_id: str) -> bool:
        """
        Actualiza el timestamp de heartbeat de un agente.

        Los agentes deben llamar esto periódicamente para indicar
        que siguen activos. Si no lo hacen, se consideran inactivos.

        Args:
            agent_id: ID del agente

        Returns:
            bool: True si se actualizó, False si el agente no existe
        """
        if agent_id in self._registry:
            self._registry[agent_id].last_heartbeat = datetime.now()
            return True
        return False

    def set_agent_status(self, agent_id: str, status: str) -> bool:
        """
        Actualiza el estado de un agente.

        Estados posibles:
        - "active": Listo para recibir mensajes
        - "busy": Procesando, puede encolar mensajes
        - "offline": No disponible

        Args:
            agent_id: ID del agente
            status: Nuevo estado

        Returns:
            bool: True si se actualizó
        """
        if agent_id in self._registry:
            self._registry[agent_id].status = status
            self._notify_listeners("agent_status_changed", {
                "agent_id": agent_id,
                "status": status
            })
            return True
        return False

    # =========================================================================
    # DESCUBRIMIENTO DE AGENTES
    # =========================================================================

    def get_agent(self, agent_id: str) -> Optional[AgentRegistration]:
        """
        Obtiene un agente específico por su ID.

        Este es el método más básico de descubrimiento: buscar por nombre.

        Args:
            agent_id: ID del agente a buscar

        Returns:
            AgentRegistration si existe, None si no
        """
        return self._registry.get(agent_id)

    def get_agent_card(self, agent_id: str) -> Optional[AgentCard]:
        """
        Obtiene la Agent Card de un agente.

        Las Agent Cards son el documento de identidad que otros agentes
        leen para saber cómo comunicarse.

        Args:
            agent_id: ID del agente

        Returns:
            AgentCard si existe, None si no
        """
        registration = self.get_agent(agent_id)
        if registration:
            return registration.agent_card
        return None

    def list_agents(self, only_active: bool = True) -> List[AgentRegistration]:
        """
        Lista todos los agentes registrados.

        Args:
            only_active: Si True, solo retorna agentes activos

        Returns:
            Lista de registros de agentes
        """
        agents = list(self._registry.values())

        if only_active:
            # Filtrar por estado y por heartbeat reciente
            cutoff = datetime.now() - timedelta(seconds=self._heartbeat_timeout)
            agents = [
                a for a in agents
                if a.status == "active" and a.last_heartbeat > cutoff
            ]

        return agents

    def find_agents_by_skill(self, skill_id: str) -> List[AgentRegistration]:
        """
        Busca agentes que tengan una skill específica.

        Este es un patrón clave de A2A: descubrir agentes por CAPACIDADES,
        no solo por nombre. Permite un acoplamiento más flexible.

        Ejemplo: Buscar todos los agentes que puedan hacer "analisis_moral"

        Args:
            skill_id: ID de la skill a buscar

        Returns:
            Lista de agentes que tienen esa skill
        """
        result = []
        for registration in self._registry.values():
            for skill in registration.agent_card.skills:
                if skill.id == skill_id:
                    result.append(registration)
                    break
        return result

    def find_agents_by_capability(self, capability: str) -> List[AgentRegistration]:
        """
        Busca agentes que tengan una capacidad específica.

        Ejemplo: Buscar agentes con "can_query_other_agents": True

        Args:
            capability: Nombre de la capacidad

        Returns:
            Lista de agentes con esa capacidad
        """
        result = []
        for registration in self._registry.values():
            caps = registration.agent_card.capabilities
            if capability in caps and caps[capability]:
                result.append(registration)
        return result

    # =========================================================================
    # SISTEMA DE NOTIFICACIONES (Observer Pattern)
    # =========================================================================

    def add_listener(self, callback: callable):
        """
        Agrega un listener para recibir notificaciones de cambios.

        Los listeners reciben notificaciones cuando:
        - Se registra un agente
        - Se elimina un agente
        - Cambia el estado de un agente

        Esto se usa para notificar a la UI web en tiempo real.

        Args:
            callback: Función async que recibe (event_type, data)
        """
        self._listeners.append(callback)

    def remove_listener(self, callback: callable):
        """Elimina un listener."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify_listeners(self, event_type: str, data: dict):
        """
        Notifica a todos los listeners de un evento.

        Args:
            event_type: Tipo de evento
            data: Datos del evento
        """
        for listener in self._listeners:
            try:
                # Los listeners pueden ser async o sync
                if asyncio.iscoroutinefunction(listener):
                    asyncio.create_task(listener(event_type, data))
                else:
                    listener(event_type, data)
            except Exception as e:
                print(f"   [Discovery] Error notificando listener: {e}")

    # =========================================================================
    # INICIALIZACIÓN
    # =========================================================================

    def register_all_agents(self):
        """
        Registra todos los agentes predefinidos.

        Esto se llama al iniciar el servidor para registrar
        los 4 agentes del sistema (sacerdote, critico, meta_critico, juez).
        """
        print("\n[Discovery] Registrando agentes predefinidos...")

        for name, card in ALL_AGENT_CARDS.items():
            self.register_agent(card)

        print(f"[Discovery] {len(ALL_AGENT_CARDS)} agentes registrados\n")

    def get_discovery_document(self) -> dict:
        """
        Genera el documento de descubrimiento del servidor.

        Este documento se expone en /.well-known/agent.json
        y lista todos los agentes disponibles.

        Returns:
            Documento JSON con información de todos los agentes
        """
        return {
            "service": "A2A Discovery Service",
            "version": "1.0.0",
            "agents": [
                {
                    "id": reg.agent_id,
                    "name": reg.agent_card.name,
                    "description": reg.agent_card.description,
                    "url": reg.agent_card.url,
                    "status": reg.status,
                    "skills": [s.id for s in reg.agent_card.skills]
                }
                for reg in self._registry.values()
            ]
        }


# ============================================================================
# INSTANCIA SINGLETON
# ============================================================================
# Usamos una instancia global para que todos los componentes
# del servidor compartan el mismo servicio de descubrimiento.
# ============================================================================

discovery_service = DiscoveryService()
