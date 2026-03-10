# agents/supervisor.py
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import InMemorySaver
import os
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
# Importar los sub-agentes que creamos
from agents.tools import agente_sacerdote, agente_critico, agente_critico_del_critico
from agents.models import VeredictoFinal, IncoherenciaDetectada, TipoIncoherencia

load_dotenv()

llm = ChatOpenAI(
    model=os.getenv("OPENAI_MODEL"),
    api_key=os.getenv("OPENAI_API_KEY"),
    temperature=0.2
)

# ====================================================
# ENVOLVER SUB-AGENTES COMO TOOLS
# ====================================================

@tool
def consultar_sacerdote(consulta: str) -> str:
    """
    Consulta al Padre sobre aspectos MORALES y ÉTICOS del libro.
    Usa esto cuando necesites análisis desde perspectiva religiosa/moral.
    El sacerdote identificará transgresiones morales, dilemas éticos, etc.
    """
    resultado = agente_sacerdote.invoke(
        {"messages": [{"role": "user", "content": consulta}]}
    )
    return resultado["messages"][-1].content


@tool
def consultar_critico(consulta: str) -> str:
    """
    Consulta al Crítico Literario sobre ESTRUCTURA NARRATIVA, desarrollo de personajes,
    coherencia interna de la trama. Usa esto para análisis técnico-literario.
    """
    resultado = agente_critico.invoke(
        {"messages": [{"role": "user", "content": consulta}]}
    )
    return resultado["messages"][-1].content


@tool
def consultar_critico_del_critico(consulta: str) -> str:
    """
    Consulta al Meta-Crítico para REFUTAR o DEFENDER las críticas previas.
    Usa esto cuando necesites contra-argumentos o perspectivas alternativas.
    Este agente defiende las licencias poéticas del autor.
    """
    resultado = agente_critico_del_critico.invoke(
        {"messages": [{"role": "user", "content": consulta}]}
    )
    return resultado["messages"][-1].content


# ====================================================
# CREAR EL SUPERVISOR (EL JUEZ)
# ====================================================

# agents/supervisor.py - reemplazar toda la función (LÍNEA ~54)

def crear_supervisor_estructurado():
    """
    Crea un supervisor que coordina los 3 agentes y devuelve JSON estructurado.
    Soporta memoria via checkpointer.
    """
    
    llm_estructurado = llm.with_structured_output(VeredictoFinal)
    memoria = InMemorySaver() 
    
    def ejecutar_analisis_completo(
        libro_info: str = None, 
        config: dict = None  
    ) -> VeredictoFinal:
        """
        Ejecuta el análisis completo consultando a los 3 agentes.
        
        Args:
            libro_info: Información adicional del libro (opcional)
            config: Dict con thread_id para memoria. Ej: {"configurable": {"thread_id": "analisis-001"}}
        """
        
        # Si no hay config, crear uno por defecto
        if config is None:
            import uuid
            config = {"configurable": {"thread_id": f"analisis-{uuid.uuid4().hex[:8]}"}}
        
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        print(f"🧵 Thread ID: {thread_id}")
        
        # PASO 1: Consultar al Sacerdote
        print("🔍 Consultando al Sacerdote...")
        config_sacerdote = {"configurable": {"thread_id": f"{thread_id}-sacerdote"}}
        resultado_sacerdote = agente_sacerdote.invoke({
            "messages": [{
                "role": "user", 
                "content": (
                    "Analiza 'Cadáver exquisito' e identifica las 3 principales "
                    "incoherencias MORALES o ÉTICAS. Usa tus herramientas."
                )
            }]
        }, config_sacerdote) 
        analisis_sacerdote = resultado_sacerdote["messages"][-1].content
        
        # PASO 2: Consultar al Crítico Literario
        print("📚 Consultando al Crítico Literario...")
        config_critico = {"configurable": {"thread_id": f"{thread_id}-critico"}}
        resultado_critico = agente_critico.invoke({
            "messages": [{
                "role": "user",
                "content": (
                    "Analiza 'Cadáver exquisito' e identifica las 3 principales "
                    "incoherencias NARRATIVAS o ESTRUCTURALES. Usa tus herramientas."
                )
            }]
        }, config_critico)
        analisis_critico = resultado_critico["messages"][-1].content
        
        # PASO 3: Consultar al Crítico del Crítico
        print("⚖️ Consultando al Meta-Crítico...")
        config_meta = {"configurable": {"thread_id": f"{thread_id}-meta"}}
        resultado_meta = agente_critico_del_critico.invoke({
            "messages": [{
                "role": "user",
                "content": (
                    f"Lee estos análisis y REFUTA lo que consideres erróneo:\n\n"
                    f"SACERDOTE: {analisis_sacerdote}\n\n"
                    f"CRÍTICO: {analisis_critico}\n\n"
                    f"Usa tus herramientas para defender las decisiones del autor."
                )
            }]
        }, config_meta)  # ← NUEVO: pasar config
        analisis_meta = resultado_meta["messages"][-1].content
        
        # PASO 4: El Juez consolida TODO
        print("👨‍⚖️ El Juez emite su veredicto...")
        
        prompt_final = f"""
Sos el JUEZ SUPREMO. Has escuchado a 3 expertos sobre 'Cadáver exquisito':

📿 SACERDOTE (análisis moral):
{analisis_sacerdote}

📖 CRÍTICO LITERARIO (análisis narrativo):
{analisis_critico}

🎭 META-CRÍTICO (defensa del autor):
{analisis_meta}

AHORA DEBÉS:
1. Identificar TODAS las incoherencias mencionadas (morales + narrativas)
2. Para cada una, determinar: ¿es real o es licencia poética?
3. Decidir quién tiene más razón: sacerdote, critico, critico_del_critico, o empate
4. Evaluar nivel de controversia del libro (1-10)
5. Dar una recomendación de lectura

IMPORTANTE: Generá una lista consolidada de incoherencias incluyendo:
- Las que el sacerdote encontró (tipo: MORAL o ETICA)
- Las que el crítico encontró (tipo: NARRATIVA o ESTRUCTURAL)
- Las que el critico del critico encontró (tipo: NARRATIVA o ESTRUCTURAL)
- Tu evaluación de si son incoherencias reales o decisiones artísticas válidas

Respondé ÚNICAMENTE con el JSON estructurado que se te solicita.
"""

        respuesta_estructurada = llm_estructurado.invoke([
            SystemMessage(content="Sos un juez imparcial. Generás veredictos estructurados."),
            HumanMessage(content=prompt_final)
        ])
        
        # Guardar en memoria (opcional, para futuras extensiones)
        # memoria.put(config, {"veredicto": respuesta_estructurada})
        
        return respuesta_estructurada
    
    return ejecutar_analisis_completo


generar_veredicto_json = crear_supervisor_estructurado()