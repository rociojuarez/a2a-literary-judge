# main.py
# ============================================================================
# PUNTO DE ENTRADA - Sistema A2A (Agent-to-Agent)
# ============================================================================
# Este archivo inicia el servidor FastAPI que expone el sistema A2A.
#
# Modos de ejecución:
# 1. python main.py          -> Inicia el servidor web
# 2. python main.py --cli    -> Ejecuta análisis en modo CLI (sin servidor)
#
# El servidor expone:
# - Interfaz web en http://localhost:8000/
# - API REST en http://localhost:8000/docs
# - WebSocket en ws://localhost:8000/ws
# ============================================================================

import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_server():
    """
    Inicia el servidor FastAPI con Uvicorn.

    El servidor se ejecuta en http://localhost:8000
    La documentación interactiva está en http://localhost:8000/docs
    """
    import uvicorn

    print("\n" + "=" * 70)
    print("🚀 SISTEMA A2A - Agent-to-Agent Protocol")
    print("=" * 70)
    print("\nIniciando servidor...")
    print("\n📍 URLs disponibles:")
    print("   • Interfaz Web:     http://localhost:8000/")
    print("   • API Docs:         http://localhost:8000/docs")
    print("   • Discovery:        http://localhost:8000/.well-known/agent.json")
    print("   • WebSocket:        ws://localhost:8000/ws")
    print("\n" + "=" * 70 + "\n")

    uvicorn.run(
        "server.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload en desarrollo
        log_level="info"
    )


def run_cli():
    """
    Ejecuta el análisis en modo CLI (sin servidor).

    Útil para testing rápido sin levantar el servidor web.
    """
    import asyncio
    import json
    from agents.models import VeredictoFinal
    from server.discovery import discovery_service
    from server.message_bus import message_bus
    from agents.a2a_agents import create_all_agents

    print("\n" + "=" * 70)
    print("🔍 ANÁLISIS A2A - Modo CLI")
    print("=" * 70 + "\n")

    # Registrar agentes
    discovery_service.register_all_agents()

    # Crear agentes
    agents = create_all_agents(message_bus, discovery_service)

    # Ejecutar análisis
    async def run_analysis():
        juez = agents["juez"]
        result = await juez.execute_skill("iniciar_analisis", {
            "libro": "Cadáver exquisito - Agustina Bazterrica"
        })
        return result

    result = asyncio.run(run_analysis())

    # Mostrar resultado de forma limpia
    print("\n" + "=" * 70)
    print("✅ VEREDICTO FINAL - JSON")
    print("=" * 70 + "\n")

    if result and "veredicto" in result:
        veredicto = result["veredicto"]
        # Si es un dict, convertirlo a JSON bonito
        if isinstance(veredicto, dict):
            print(json.dumps(veredicto, indent=2, ensure_ascii=False))
        else:
            # Si es un objeto Pydantic, usar model_dump_json
            try:
                print(veredicto.model_dump_json(indent=2, ensure_ascii=False))
            except:
                print(json.dumps(veredicto, indent=2, ensure_ascii=False, default=str))
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

    print("\n" + "=" * 70 + "\n")


def main():
    """
    Punto de entrada principal.

    Argumentos:
        --cli: Ejecutar en modo CLI (sin servidor)
        --help: Mostrar ayuda
    """
    if "--help" in sys.argv or "-h" in sys.argv:
        print("""
Sistema A2A - Agent-to-Agent Protocol

Uso:
    python main.py          Inicia el servidor web (default)
    python main.py --cli    Ejecuta análisis en modo CLI
    python main.py --help   Muestra esta ayuda

Descripción:
    Sistema multi-agente para análisis literario usando el
    protocolo A2A (Agent-to-Agent) de Google.

    Agentes disponibles:
    - Sacerdote:    Análisis moral y ético
    - Crítico:      Análisis narrativo y estructural
    - Meta-Crítico: Defensa de decisiones artísticas
    - Juez:         Coordinador y emisor del veredicto

Requisitos:
    - Python 3.9+
    - Variables de entorno en .env (OPENAI_API_KEY)
    - Dependencias: pip install -r requirements.txt
        """)
        return

    if "--cli" in sys.argv:
        run_cli()
    else:
        run_server()


if __name__ == "__main__":
    main()
