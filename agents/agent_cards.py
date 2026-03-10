# agents/agent_cards.py
# ============================================================================
# DEFINICIONES DE AGENT CARDS
# ============================================================================
# Este archivo define las "tarjetas de identidad" de cada agente.
# Las Agent Cards son el estándar del protocolo A2A para describir
# qué puede hacer cada agente y cómo comunicarse con él.
#
# Cada agente expone su card en: /agent/{nombre}/.well-known/agent.json
# Otros agentes leen estas cards para saber cómo interactuar.
# ============================================================================

from agents.models import AgentCard, AgentSkill

# URL base del servidor (se actualiza dinámicamente al iniciar)
BASE_URL = "http://localhost:8000"


def get_base_url():
    """Retorna la URL base actual del servidor."""
    return BASE_URL


def set_base_url(url: str):
    """Actualiza la URL base (útil para deployment)."""
    global BASE_URL
    BASE_URL = url


# ============================================================================
# AGENT CARD: SACERDOTE
# ============================================================================
# El Sacerdote analiza aspectos morales y éticos desde perspectiva religiosa.
# Puede detectar transgresiones morales, conflictos éticos, etc.
# ============================================================================

SACERDOTE_CARD = AgentCard(
    name="sacerdote",
    description=(
        "Agente especializado en análisis MORAL y ÉTICO desde perspectiva religiosa católica. "
        "Identifica transgresiones morales, dilemas éticos, y conflictos con la doctrina cristiana "
        "en obras literarias. Riguroso pero comprensivo con la expresión artística."
    ),
    url=f"{BASE_URL}/agent/sacerdote",
    version="1.0.0",
    author="Equipo A2A - Henry",
    skills=[
        AgentSkill(
            id="analisis_moral",
            name="Análisis Moral",
            description=(
                "Analiza las implicaciones morales de un texto desde la perspectiva "
                "de la doctrina católica. Identifica transgresiones, cita referencias bíblicas."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "texto": {"type": "string", "description": "Texto o fragmento a analizar"},
                    "contexto": {"type": "string", "description": "Contexto adicional del libro"}
                },
                "required": ["texto"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "analisis": {"type": "string"},
                    "transgresiones": {"type": "array", "items": {"type": "string"}},
                    "severidad": {"type": "integer", "minimum": 1, "maximum": 10}
                }
            }
        ),
        AgentSkill(
            id="detectar_incoherencias_eticas",
            name="Detectar Incoherencias Éticas",
            description=(
                "Busca incoherencias éticas en la narrativa: personajes que actúan "
                "de forma inconsistente con sus valores declarados, contradicciones morales, etc."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "libro": {"type": "string", "description": "Nombre del libro"},
                    "pregunta": {"type": "string", "description": "Pregunta específica a responder"}
                },
                "required": ["libro"]
            },
            output_schema={
                "type": "object",
                "properties": {
                    "incoherencias": {"type": "array"},
                    "veredicto": {"type": "string"}
                }
            }
        ),
        AgentSkill(
            id="responder_consulta",
            name="Responder Consulta",
            description="Responde preguntas de otros agentes sobre su análisis.",
            input_schema={
                "type": "object",
                "properties": {
                    "pregunta": {"type": "string"},
                    "contexto_previo": {"type": "string"}
                },
                "required": ["pregunta"]
            }
        )
    ],
    capabilities={
        "streaming": False,
        "push_notifications": False,
        "state_transition_history": True,
        "can_query_other_agents": True  # Puede consultar a otros agentes
    }
)


# ============================================================================
# AGENT CARD: CRÍTICO LITERARIO
# ============================================================================
# El Crítico analiza aspectos técnicos: estructura narrativa, desarrollo
# de personajes, coherencia interna, técnicas literarias, etc.
# ============================================================================

CRITICO_CARD = AgentCard(
    name="critico",
    description=(
        "Agente especializado en análisis NARRATIVO y ESTRUCTURAL de obras literarias. "
        "Evalúa técnica narrativa, coherencia interna, desarrollo de personajes, "
        "punto de vista, manejo del tiempo, y otros aspectos técnico-literarios. "
        "Exigente pero justo en sus evaluaciones."
    ),
    url=f"{BASE_URL}/agent/critico",
    version="1.0.0",
    author="Equipo A2A - Henry",
    skills=[
        AgentSkill(
            id="analisis_estructura",
            name="Análisis de Estructura Narrativa",
            description=(
                "Analiza la estructura narrativa: punto de vista, tiempo narrativo, "
                "coherencia interna, técnicas empleadas."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "aspecto": {
                        "type": "string",
                        "enum": ["punto_de_vista", "tiempo_narrativo", "coherencia_interna", "general"]
                    },
                    "libro": {"type": "string"}
                },
                "required": ["aspecto"]
            }
        ),
        AgentSkill(
            id="analisis_personajes",
            name="Análisis de Personajes",
            description=(
                "Evalúa el desarrollo y coherencia de personajes: "
                "evolución psicológica, consistencia, profundidad."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "personaje": {"type": "string", "description": "Nombre del personaje"},
                    "libro": {"type": "string"}
                },
                "required": ["personaje"]
            }
        ),
        AgentSkill(
            id="detectar_incoherencias_narrativas",
            name="Detectar Incoherencias Narrativas",
            description="Identifica problemas estructurales, plot holes, inconsistencias.",
            input_schema={
                "type": "object",
                "properties": {
                    "libro": {"type": "string"}
                },
                "required": ["libro"]
            }
        ),
        AgentSkill(
            id="responder_consulta",
            name="Responder Consulta",
            description="Responde preguntas de otros agentes sobre su análisis.",
            input_schema={
                "type": "object",
                "properties": {
                    "pregunta": {"type": "string"},
                    "contexto_previo": {"type": "string"}
                },
                "required": ["pregunta"]
            }
        )
    ],
    capabilities={
        "streaming": False,
        "push_notifications": False,
        "state_transition_history": True,
        "can_query_other_agents": True
    }
)


# ============================================================================
# AGENT CARD: META-CRÍTICO (Crítico del Crítico)
# ============================================================================
# El Meta-Crítico defiende las decisiones artísticas del autor.
# Refuta críticas que confunden licencias poéticas con errores.
# ============================================================================

META_CRITICO_CARD = AgentCard(
    name="meta_critico",
    description=(
        "Agente META-CRÍTICO posmoderno. Defiende la libertad creativa y las "
        "decisiones artísticas del autor. Refuta críticas reduccionistas que "
        "confunden licencias poéticas intencionales con errores técnicos. "
        "Contextualiza obras en tradiciones literarias más amplias."
    ),
    url=f"{BASE_URL}/agent/meta_critico",
    version="1.0.0",
    author="Equipo A2A - Henry",
    skills=[
        AgentSkill(
            id="defender_licencia_poetica",
            name="Defender Licencia Poética",
            description=(
                "Argumenta por qué una 'incoherencia' señalada es en realidad "
                "una decisión artística válida. Compara con técnicas similares "
                "usadas por autores consagrados."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "critica": {"type": "string", "description": "La crítica a refutar"},
                    "libro": {"type": "string"}
                },
                "required": ["critica"]
            }
        ),
        AgentSkill(
            id="contra_argumentar",
            name="Contra-Argumentar",
            description=(
                "Genera contra-argumentos sólidos a críticas morales o narrativas. "
                "Distingue entre representar algo y aprobarlo."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "argumento": {"type": "string", "description": "Argumento a refutar"},
                    "tipo": {"type": "string", "enum": ["moral", "narrativo"]}
                },
                "required": ["argumento"]
            }
        ),
        AgentSkill(
            id="consultar_agente",
            name="Consultar Otro Agente",
            description=(
                "Permite al meta-crítico consultar directamente a otro agente "
                "para obtener clarificaciones antes de refutar."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "agente_destino": {"type": "string"},
                    "pregunta": {"type": "string"}
                },
                "required": ["agente_destino", "pregunta"]
            }
        ),
        AgentSkill(
            id="responder_consulta",
            name="Responder Consulta",
            description="Responde preguntas de otros agentes.",
            input_schema={
                "type": "object",
                "properties": {
                    "pregunta": {"type": "string"}
                },
                "required": ["pregunta"]
            }
        )
    ],
    capabilities={
        "streaming": False,
        "push_notifications": False,
        "state_transition_history": True,
        "can_query_other_agents": True  # Skill principal: consultar a otros
    }
)


# ============================================================================
# AGENT CARD: JUEZ (Orquestador/Supervisor)
# ============================================================================
# El Juez coordina el análisis, consulta a todos los agentes,
# y emite el veredicto final consolidado.
# ============================================================================

JUEZ_CARD = AgentCard(
    name="juez",
    description=(
        "Agente JUEZ/SUPERVISOR. Coordina el análisis multi-agente, consulta a "
        "los expertos (sacerdote, crítico, meta-crítico), evalúa sus argumentos, "
        "y emite un veredicto final consolidado. Imparcial y riguroso."
    ),
    url=f"{BASE_URL}/agent/juez",
    version="1.0.0",
    author="Equipo A2A - Henry",
    skills=[
        AgentSkill(
            id="iniciar_analisis",
            name="Iniciar Análisis Completo",
            description=(
                "Inicia un análisis completo de un libro, consultando a todos "
                "los agentes expertos y consolidando sus opiniones."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "libro": {"type": "string", "description": "Nombre del libro a analizar"},
                    "enfoque": {
                        "type": "string",
                        "description": "Enfoque específico (opcional)",
                        "enum": ["completo", "moral", "narrativo", "controversia"]
                    }
                },
                "required": ["libro"]
            },
            output_schema={
                "type": "object",
                "description": "VeredictoFinal estructurado"
            }
        ),
        AgentSkill(
            id="consultar_experto",
            name="Consultar Experto",
            description="Consulta a un agente experto específico.",
            input_schema={
                "type": "object",
                "properties": {
                    "agente": {"type": "string", "enum": ["sacerdote", "critico", "meta_critico"]},
                    "pregunta": {"type": "string"}
                },
                "required": ["agente", "pregunta"]
            }
        ),
        AgentSkill(
            id="emitir_veredicto",
            name="Emitir Veredicto",
            description="Consolida los análisis y emite el veredicto final estructurado.",
            input_schema={
                "type": "object",
                "properties": {
                    "analisis_sacerdote": {"type": "string"},
                    "analisis_critico": {"type": "string"},
                    "analisis_meta": {"type": "string"}
                },
                "required": ["analisis_sacerdote", "analisis_critico", "analisis_meta"]
            }
        )
    ],
    capabilities={
        "streaming": False,
        "push_notifications": True,  # El juez puede notificar progreso
        "state_transition_history": True,
        "can_query_other_agents": True,
        "is_orchestrator": True  # Marca especial: es el orquestador
    }
)


# ============================================================================
# REGISTRO DE TODAS LAS CARDS (para fácil acceso)
# ============================================================================

ALL_AGENT_CARDS = {
    "sacerdote": SACERDOTE_CARD,
    "critico": CRITICO_CARD,
    "meta_critico": META_CRITICO_CARD,
    "juez": JUEZ_CARD
}


def get_agent_card(agent_name: str) -> AgentCard:
    """Obtiene la Agent Card de un agente por su nombre."""
    if agent_name not in ALL_AGENT_CARDS:
        raise ValueError(f"Agente '{agent_name}' no encontrado. Disponibles: {list(ALL_AGENT_CARDS.keys())}")
    return ALL_AGENT_CARDS[agent_name]


def update_all_urls(base_url: str):
    """Actualiza las URLs de todas las Agent Cards."""
    set_base_url(base_url)
    for name, card in ALL_AGENT_CARDS.items():
        card.url = f"{base_url}/agent/{name}"
