# agents/grafo_a2a.py
# ============================================================================
# GRAFO A2A (Agent to Agent) - Sistema Multi-Agente con LangGraph
# ============================================================================
# Este archivo implementa el patrón de grafo para coordinar múltiples agentes.
# En lugar de llamar a los agentes secuencialmente en una función,
# usamos un StateGraph que define explícitamente el flujo de datos.
#
# VENTAJAS DE USAR GRAFO:
# 1. Visualización clara del flujo
# 2. Fácil de modificar (agregar/quitar nodos)
# 3. Mejor debugging (puedes ver el estado en cada paso)
# 4. Permite flujos condicionales (si quisieras agregar lógica de decisión)
# ============================================================================

from typing import TypedDict, Optional
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
import os
from dotenv import load_dotenv

# Importamos los agentes que ya tienes definidos
from agents.tools import agente_sacerdote, agente_critico, agente_critico_del_critico
from agents.models import VeredictoFinal

load_dotenv()

# ============================================================================
# PASO 1: DEFINIR EL ESTADO
# ============================================================================
# El Estado es un TypedDict que define TODOS los datos que fluyen por el grafo.
# Piénsalo como una "caja" que pasa de nodo en nodo, acumulando información.
#
# Cada nodo puede:
#   - LEER cualquier campo del estado
#   - ESCRIBIR/ACTUALIZAR campos retornando un diccionario
#
# IMPORTANTE: El estado se va "llenando" a medida que avanza por los nodos.
# Al inicio solo tiene 'libro', al final tiene todo completo.
# ============================================================================

class EstadoAnalisisA2A(TypedDict):
    """
    Estado que fluye a través del grafo A2A.

    Campos:
    - libro: Nombre del libro a analizar (entrada inicial)
    - thread_id: Identificador único de la sesión (para memoria)
    - analisis_sacerdote: Resultado del agente sacerdote
    - analisis_critico: Resultado del agente crítico literario
    - analisis_meta: Resultado del agente crítico del crítico
    - veredicto_final: Resultado consolidado por el juez (salida final)
    """
    libro: str
    thread_id: str
    analisis_sacerdote: Optional[str]
    analisis_critico: Optional[str]
    analisis_meta: Optional[str]
    veredicto_final: Optional[VeredictoFinal]


# ============================================================================
# PASO 2: DEFINIR LOS NODOS
# ============================================================================
# Cada nodo es una función que:
#   1. Recibe el estado actual como parámetro
#   2. Hace algún procesamiento (llamar a un agente, transformar datos, etc.)
#   3. Retorna un diccionario con los campos que quiere ACTUALIZAR
#
# IMPORTANTE: No necesitas retornar TODO el estado, solo lo que cambió.
# LangGraph automáticamente hace el "merge" con el estado existente.
# ============================================================================

def nodo_consulta_sacerdote(estado: EstadoAnalisisA2A) -> dict:
    """
    NODO 1: Consulta al Agente Sacerdote

    Este nodo invoca al agente sacerdote para obtener un análisis
    desde la perspectiva moral/ética/religiosa.

    Input del estado: libro, thread_id
    Output al estado: analisis_sacerdote
    """
    print("=" * 60)
    print("📿 NODO: Consultando al Sacerdote...")
    print("=" * 60)

    # Preparamos la configuración con thread_id para la memoria
    config = {"configurable": {"thread_id": f"{estado['thread_id']}-sacerdote"}}

    # Invocamos al agente sacerdote
    # El agente usa sus tools (analizar_moral_canibalismo, analizar_rol_mujer)
    resultado = agente_sacerdote.invoke({
        "messages": [{
            "role": "user",
            "content": (
                f"Analiza '{estado['libro']}' e identifica las 3 principales "
                "incoherencias MORALES o ÉTICAS. Usa tus herramientas para fundamentar."
            )
        }]
    }, config)

    # Extraemos el contenido del último mensaje (la respuesta del agente)
    analisis = resultado["messages"][-1].content

    print(f"   Respuesta del Sacerdote: {len(analisis)} caracteres")

    # Retornamos SOLO el campo que queremos actualizar
    # LangGraph hace merge automático con el resto del estado
    return {"analisis_sacerdote": analisis}


def nodo_consulta_critico(estado: EstadoAnalisisA2A) -> dict:
    """
    NODO 2: Consulta al Agente Crítico Literario

    Este nodo invoca al agente crítico para obtener un análisis
    técnico-narrativo del libro.

    Input del estado: libro, thread_id
    Output al estado: analisis_critico
    """
    print("=" * 60)
    print("📚 NODO: Consultando al Crítico Literario...")
    print("=" * 60)

    config = {"configurable": {"thread_id": f"{estado['thread_id']}-critico"}}

    resultado = agente_critico.invoke({
        "messages": [{
            "role": "user",
            "content": (
                f"Analiza '{estado['libro']}' e identifica las 3 principales "
                "incoherencias NARRATIVAS o ESTRUCTURALES. Usa tus herramientas."
            )
        }]
    }, config)

    analisis = resultado["messages"][-1].content

    print(f"   Respuesta del Crítico: {len(analisis)} caracteres")

    return {"analisis_critico": analisis}


def nodo_consulta_meta_critico(estado: EstadoAnalisisA2A) -> dict:
    """
    NODO 3: Consulta al Agente Meta-Crítico (Crítico del Crítico)

    Este nodo es especial porque NECESITA los análisis previos.
    El meta-crítico refuta/defiende lo que dijeron los otros agentes.

    Input del estado: libro, thread_id, analisis_sacerdote, analisis_critico
    Output al estado: analisis_meta

    NOTA: Aquí se ve el poder del grafo - podemos acceder a los
    resultados de nodos anteriores porque están en el estado.
    """
    print("=" * 60)
    print("🎭 NODO: Consultando al Meta-Crítico...")
    print("=" * 60)

    config = {"configurable": {"thread_id": f"{estado['thread_id']}-meta"}}

    # Aquí usamos los análisis previos del estado
    # Esto solo es posible porque los nodos anteriores ya los calcularon
    resultado = agente_critico_del_critico.invoke({
        "messages": [{
            "role": "user",
            "content": (
                f"Lee estos análisis de '{estado['libro']}' y REFUTA lo que "
                f"consideres erróneo:\n\n"
                f"SACERDOTE dice:\n{estado['analisis_sacerdote']}\n\n"
                f"CRÍTICO dice:\n{estado['analisis_critico']}\n\n"
                f"Usa tus herramientas para defender las decisiones del autor."
            )
        }]
    }, config)

    analisis = resultado["messages"][-1].content

    print(f"   Respuesta del Meta-Crítico: {len(analisis)} caracteres")

    return {"analisis_meta": analisis}


def nodo_veredicto_juez(estado: EstadoAnalisisA2A) -> dict:
    """
    NODO 4: El Juez emite el Veredicto Final

    Este es el nodo final que consolida TODO y genera el JSON estructurado.
    Usa with_structured_output para garantizar que la salida sea un VeredictoFinal.

    Input del estado: TODOS los análisis previos
    Output al estado: veredicto_final (VeredictoFinal)
    """
    print("=" * 60)
    print("👨‍⚖️ NODO: El Juez emite su veredicto...")
    print("=" * 60)

    # Creamos un LLM con salida estructurada
    # Esto garantiza que la respuesta sea un objeto VeredictoFinal válido
    llm = ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        api_key=os.getenv("OPENAI_API_KEY"),
        temperature=0.2
    )
    llm_estructurado = llm.with_structured_output(VeredictoFinal)

    # Construimos el prompt con TODOS los análisis
    prompt_final = f"""
Sos el JUEZ SUPREMO. Has escuchado a 3 expertos sobre '{estado['libro']}':

📿 SACERDOTE (análisis moral):
{estado['analisis_sacerdote']}

📖 CRÍTICO LITERARIO (análisis narrativo):
{estado['analisis_critico']}

🎭 META-CRÍTICO (defensa del autor):
{estado['analisis_meta']}

AHORA DEBÉS:
1. Identificar TODAS las incoherencias mencionadas (morales + narrativas)
2. Para cada una, determinar: ¿es real o es licencia poética?
3. Decidir quién tiene más razón: sacerdote, critico, critico_del_critico, o empate
4. Evaluar nivel de controversia del libro (1-10)
5. Dar una recomendación de lectura

IMPORTANTE: Generá una lista consolidada de incoherencias incluyendo:
- Las que el sacerdote encontró (tipo: MORAL o ETICA)
- Las que el crítico encontró (tipo: NARRATIVA o ESTRUCTURAL)
- Tu evaluación de si son incoherencias reales o decisiones artísticas válidas

Respondé ÚNICAMENTE con el JSON estructurado que se te solicita.
"""

    # Invocamos al LLM estructurado
    veredicto = llm_estructurado.invoke([
        SystemMessage(content="Sos un juez imparcial. Generás veredictos estructurados."),
        HumanMessage(content=prompt_final)
    ])

    print(f"   Veredicto generado con {len(veredicto.todas_las_incoherencias)} incoherencias")

    return {"veredicto_final": veredicto}


# ============================================================================
# PASO 3: CONSTRUIR EL GRAFO
# ============================================================================
# Ahora conectamos todo:
# 1. Creamos el StateGraph con nuestro tipo de estado
# 2. Agregamos cada nodo con add_node("nombre", funcion)
# 3. Conectamos nodos con add_edge(origen, destino)
# 4. Compilamos el grafo
#
# START y END son nodos especiales de LangGraph que marcan inicio/fin
# ============================================================================

def construir_grafo_a2a():
    """
    Construye y retorna el grafo A2A compilado.

    El flujo es:
    START -> sacerdote -> critico -> meta_critico -> veredicto -> END

    Este es un grafo SECUENCIAL (cada nodo después del otro).
    LangGraph también permite grafos con bifurcaciones y condiciones,
    pero para este caso un flujo lineal es suficiente.
    """

    # 1. Crear el builder del grafo con nuestro tipo de estado
    builder = StateGraph(EstadoAnalisisA2A)

    # 2. Agregar los nodos
    # Cada nodo tiene un nombre (string) y una función asociada
    builder.add_node("consulta_sacerdote", nodo_consulta_sacerdote)
    builder.add_node("consulta_critico", nodo_consulta_critico)
    builder.add_node("consulta_meta_critico", nodo_consulta_meta_critico)
    builder.add_node("veredicto_juez", nodo_veredicto_juez)

    # 3. Conectar los nodos con edges (aristas)
    # START es el punto de entrada especial de LangGraph
    builder.add_edge(START, "consulta_sacerdote")

    # Flujo secuencial: sacerdote -> critico -> meta -> veredicto
    builder.add_edge("consulta_sacerdote", "consulta_critico")
    builder.add_edge("consulta_critico", "consulta_meta_critico")
    builder.add_edge("consulta_meta_critico", "veredicto_juez")

    # END es el punto de salida especial de LangGraph
    builder.add_edge("veredicto_juez", END)

    # 4. Compilar el grafo
    # Esto valida que todo esté bien conectado y crea el grafo ejecutable
    grafo = builder.compile()

    return grafo


# ============================================================================
# PASO 4: FUNCIÓN PARA VISUALIZAR EL GRAFO
# ============================================================================
# LangGraph puede generar visualizaciones del grafo en varios formatos.
# Esto es MUY útil para debugging y para mostrar en presentaciones.
# ============================================================================

def visualizar_grafo(grafo):
    """
    Visualiza el grafo en formato ASCII o imagen PNG.

    Intenta primero generar PNG (requiere graphviz instalado),
    si falla usa ASCII que siempre funciona.
    """
    print("\n" + "=" * 60)
    print("📊 VISUALIZACIÓN DEL GRAFO A2A")
    print("=" * 60 + "\n")

    try:
        # Intentar generar imagen PNG (requiere graphviz)
        # Esto es lo que usa el profesor con draw_mermaid_png()
        from IPython.display import display, Image
        png_data = grafo.get_graph().draw_mermaid_png()

        # Guardar la imagen
        with open("grafo_a2a.png", "wb") as f:
            f.write(png_data)
        print("   Imagen guardada en: grafo_a2a.png")

        # Si estamos en Jupyter, mostrar inline
        try:
            display(Image(png_data))
        except:
            pass

    except Exception as e:
        # Si falla, usar ASCII (siempre funciona)
        print("   (PNG no disponible, mostrando ASCII)\n")
        print(grafo.get_graph().draw_ascii())


# ============================================================================
# PASO 5: FUNCIÓN PRINCIPAL PARA EJECUTAR EL ANÁLISIS
# ============================================================================
# Esta función es el punto de entrada para usar el grafo.
# Crea el estado inicial, ejecuta el grafo, y retorna el resultado.
# ============================================================================

def ejecutar_analisis_con_grafo(
    libro: str = "Cadáver exquisito - Agustina Bazterrica",
    thread_id: str = None,
    mostrar_grafo: bool = True
) -> VeredictoFinal:
    """
    Ejecuta el análisis multi-agente usando el grafo A2A.

    Args:
        libro: Nombre del libro a analizar
        thread_id: ID único para la sesión (se genera automáticamente si no se provee)
        mostrar_grafo: Si True, visualiza el grafo antes de ejecutar

    Returns:
        VeredictoFinal: El veredicto estructurado del análisis
    """
    import uuid

    # Generar thread_id si no se provee
    if thread_id is None:
        thread_id = f"analisis-{uuid.uuid4().hex[:8]}"

    print(f"\n🧵 Thread ID: {thread_id}")

    # Construir el grafo
    grafo = construir_grafo_a2a()

    # Visualizar el grafo (opcional)
    if mostrar_grafo:
        visualizar_grafo(grafo)

    # Preparar el estado inicial
    # Solo necesitamos los campos de entrada, el resto se llena durante la ejecución
    estado_inicial = {
        "libro": libro,
        "thread_id": thread_id,
        "analisis_sacerdote": None,
        "analisis_critico": None,
        "analisis_meta": None,
        "veredicto_final": None
    }

    print("\n" + "=" * 60)
    print("🚀 INICIANDO EJECUCIÓN DEL GRAFO A2A")
    print("=" * 60 + "\n")

    # Ejecutar el grafo
    # invoke() ejecuta todos los nodos en orden y retorna el estado final
    estado_final = grafo.invoke(estado_inicial)

    print("\n" + "=" * 60)
    print("✅ GRAFO COMPLETADO")
    print("=" * 60 + "\n")

    # Retornar el veredicto del estado final
    return estado_final["veredicto_final"]


# ============================================================================
# CREAR INSTANCIA DEL GRAFO (para importar desde otros módulos)
# ============================================================================

grafo_a2a = construir_grafo_a2a()
