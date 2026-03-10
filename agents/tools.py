# agents/tools.py - VERSIÓN CON LLM REAL
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import InMemorySaver
import os
from dotenv import load_dotenv

load_dotenv()

# Modelo base para los tools
llm = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=os.getenv("OPENAI_API_KEY"),
    temperature=0.7
)

# ========================================
# TOOLS PARA EL AGENTE SACERDOTE
# ========================================

@tool
def analizar_moral_canibalismo(fragmento: str) -> str:
    """Analiza las implicaciones morales del canibalismo industrial desde perspectiva religiosa.
    Usa esta herramienta cuando necesites evaluar aspectos morales del libro."""
    
    # ← AHORA CONSULTA AL LLM EN VEZ DE HARDCODEAR
    prompt = f"""
Eres un teólogo católico conservador. Analiza las implicaciones morales del canibalismo 
industrial presentado en 'Cadáver exquisito' de Agustina Bazterrica.

CONTEXTO DEL LIBRO:
{fragmento}

TAREA:
1. Identifica qué enseñanzas cristianas/bíblicas son transgredidas
2. Cita pasajes bíblicos relevantes (Génesis, Levítico, Corintios, etc.)
3. Explica el nivel de transgresión moral
4. Formato: breve, riguroso, con referencias específicas

Responde en español, máximo 200 palabras.
"""
    
    respuesta = llm.invoke(prompt)
    return f"📿 ANÁLISIS MORAL - Canibalismo:\n\n{respuesta.content}"


@tool
def analizar_rol_mujer(fragmento: str) -> str:
    """Analiza el tratamiento de la mujer desde perspectiva religiosa tradicional."""
    
    # ← CONSULTA AL LLM
    prompt = f"""
Eres un teólogo católico. Analiza cómo 'Cadáver exquisito' representa a las mujeres 
desde la perspectiva de la doctrina cristiana sobre la dignidad humana.

CONTEXTO:
{fragmento}

TAREA:
1. Identifica cómo son tratadas las mujeres en la novela
2. Contrasta con enseñanzas sobre dignidad femenina (Génesis 1:27, Gálatas 3:28)
3. Detecta incoherencias entre denuncia y naturalización
4. Sé conciso y fundamentado

Español, máximo 150 palabras.
"""
    
    respuesta = llm.invoke(prompt)
    return f"📿 ANÁLISIS - Rol de la Mujer:\n\n{respuesta.content}"


# Crear el agente Sacerdote
agente_sacerdote = create_react_agent(
    llm,
    tools=[analizar_moral_canibalismo, analizar_rol_mujer],
    prompt=(
        "Eres un SACERDOTE CATÓLICO conservador analizando 'Cadáver exquisito'. "
        "Tu tarea es identificar incoherencias MORALES y ÉTICAS desde la doctrina cristiana. "
        "Eres riguroso pero comprensivo con la literatura como expresión artística. "
        "Usa tus herramientas para fundamentar tu análisis. "
        "IMPORTANTE: Pasa contexto del libro a los tools para que analicen específicamente. "
        "Responde en español."
    ),
    checkpointer=InMemorySaver(),
    name="sacerdote"
)

# ========================================
# TOOLS PARA EL CRÍTICO DE LITERATURA
# ========================================

@tool
def analizar_estructura_narrativa(aspecto: str) -> str:
    """Analiza la estructura narrativa del libro: punto de vista, tiempo, coherencia.
    
    Args:
        aspecto: Qué aspecto analizar - opciones válidas:
                'punto_de_vista', 'tiempo_narrativo', 'coherencia_interna'
    """
    
    # ← CONSULTA AL LLM
    prompt = f"""
Eres un crítico literario especializado en narrativa contemporánea.

Analiza la ESTRUCTURA NARRATIVA de 'Cadáver exquisito' de Agustina Bazterrica 
específicamente en: {aspecto}

CONTEXTO DEL LIBRO:
- Narrado en primera persona por Marcos Tejo
- Capítulos intercalados sobre "la mujer" en tercera persona
- Distopía donde se cría humanos para consumo
- Marcos trabaja en un frigorífico de "cabezas"

TAREA:
1. Analiza el aspecto solicitado ({aspecto})
2. Identifica incoherencias narrativas REALES (no decisiones artísticas válidas)
3. Evalúa si afectan la calidad literaria
4. Sé técnico pero claro

Español, máximo 200 palabras.
"""
    
    respuesta = llm.invoke(prompt)
    return f"📖 ESTRUCTURA - {aspecto.upper()}:\n\n{respuesta.content}"


@tool
def analizar_desarrollo_personajes(personaje: str) -> str:
    """Analiza la coherencia en el desarrollo de personajes.
    
    Args:
        personaje: Nombre del personaje a analizar (ej: 'Marcos Tejo', 'la mujer')
    """
    
    # ← CONSULTA AL LLM
    prompt = f"""
Eres un crítico literario. Analiza el desarrollo del personaje "{personaje}" 
en 'Cadáver exquisito'.

CONTEXTO:
- Marcos Tejo: protagonista, trabaja en frigorífico, se enamora de una "cabeza"
- La mujer: sin nombre, criada como ganado, objeto del deseo de Marcos

TAREA para "{personaje}":
1. Evalúa coherencia psicológica del personaje
2. ¿Su evolución es creíble o abrupta?
3. ¿Hay contradicciones en su caracterización?
4. Diferencia errores técnicos vs decisiones artísticas

Español, máximo 200 palabras.
"""
    
    respuesta = llm.invoke(prompt)
    return f"📖 PERSONAJE - {personaje}:\n\n{respuesta.content}"


# Crear el agente Crítico
agente_critico = create_react_agent(
    llm,
    tools=[analizar_estructura_narrativa, analizar_desarrollo_personajes],
    prompt=(
        "Eres un CRÍTICO LITERARIO especializado en narrativa contemporánea. "
        "Analizás 'Cadáver exquisito' desde técnica narrativa, coherencia interna, "
        "desarrollo de personajes. Sos exigente pero justo. "
        "Identificás incoherencias NARRATIVAS y ESTRUCTURALES reales, no confundas "
        "decisiones artísticas válidas con errores técnicos. "
        "Usá tus herramientas para profundizar el análisis. "
        "IMPORTANTE: Especifica qué aspecto/personaje quieres analizar al llamar tools. "
        "Español."
    ),
    checkpointer=InMemorySaver(),
    name="critico_literario"
)

# ========================================
# TOOLS PARA EL CRÍTICO DEL CRÍTICO
# ========================================

@tool
def defender_licencia_poetica(critica: str) -> str:
    """Defiende las 'incoherencias' como licencias poéticas intencionales.
    
    Args:
        critica: La crítica que se quiere refutar
    """
    
    # ← CONSULTA AL LLM
    prompt = f"""
Eres un meta-crítico posmoderno, defensor de la libertad creativa.

CRÍTICA RECIBIDA:
{critica}

TAREA:
Re-interpreta esa "incoherencia" como una DECISIÓN ARTÍSTICA VÁLIDA de Bazterrica:

1. ¿Por qué podría ser intencional?
2. ¿Qué efecto busca lograr?
3. Compara con autores que usan técnicas similares (Kafka, Orwell, Atwood)
4. Argumenta por qué NO es un error sino una elección

Sé convincente pero fundamentado. Español, máximo 200 palabras.
"""
    
    respuesta = llm.invoke(prompt)
    return f"🎭 DEFENSA ARTÍSTICA:\n\n{respuesta.content}"


@tool
def contra_argumentar_moral(argumento_moral: str) -> str:
    """Contra-argumenta las objeciones morales del sacerdote.
    
    Args:
        argumento_moral: El argumento moral que se quiere refutar
    """
    
    # ← CONSULTA AL LLM
    prompt = f"""
Eres un crítico literario que entiende que MOSTRAR violencia ≠ APROBARLA.

ARGUMENTO MORAL A REFUTAR:
{argumento_moral}

TAREA:
1. Explica por qué confundir representación con apología es un error crítico
2. Da ejemplos de obras clásicas que muestran inmoralidad sin ser inmorales 
   (1984, Un mundo feliz, Lolita, etc.)
3. Argumenta que la crudeza es parte del mensaje de denuncia
4. Diferencia moral del contenido vs calidad literaria

Español, máximo 200 palabras.
"""
    
    respuesta = llm.invoke(prompt)
    return f"⚖️ CONTRA-ARGUMENTO:\n\n{respuesta.content}"


# Crear el Crítico del Crítico
agente_critico_del_critico = create_react_agent(
    llm,
    tools=[defender_licencia_poetica, contra_argumentar_moral],
    prompt=(
        "Sos un META-CRÍTICO posmoderno. Tu trabajo es REFUTAR al crítico literario "
        "y al sacerdote, mostrando que sus 'incoherencias' son decisiones artísticas válidas. "
        "Defendés la libertad creativa pero con argumentos sólidos. "
        "Cuestionás las lecturas reduccionistas. "
        "IMPORTANTE: Lee cuidadosamente los argumentos antes de refutarlos. "
        "Español."
    ),
    checkpointer=InMemorySaver(),
    name="critico_del_critico"
)