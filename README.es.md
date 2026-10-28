# Trifecta Checker

[English](README.md) · [日本語](README.ja.md) · [中文](README.zh.md) · [हिन्दी](README.hi.md) · **Español**

**Una revisión de seguridad previa al vuelo para agentes de IA.** Describe lo que tu agente puede hacer —
Trifecta Checker te dice si esa combinación de poderes es segura, por qué,
y cómo dividirla si no lo es.

Construido para el Meta Global AI Developer Hackathon (oct–nov 2026).

**Demostración en vivo:** https://meta-global-ai-hackathon-trifecta-c.vercel.app/


## Cómo es usarlo

Chateas con **Trafica**, un personaje verificador amable — sin formularios, sin
necesidad de vocabulario de seguridad:

1. **Describe tu agente con tus propias palabras.** Escríbelo, pulsa 🎤 y habla, o
   pulsa + y carga un archivo: una descripción en texto plano, o una **configuración
   JSON de MCP** — sus servidores se resumen en una descripción
   y se analizan tal cual (prueba `fixtures/sample_mcp_config.json`).
2. **Recibe un veredicto en palabras sencillas** — Low, Risky o Lethal — con los poderes
   que lo sustentan y una explicación en lenguaje cotidiano de lo que podría salir mal
   y cómo solucionarlo.
3. **Si un detalle pudiera cambiar el veredicto, Trafica te hace una pregunta**
   en lugar de adivinar. Responde con un toque o escribiendo.
4. **Sigue conversando.** Pregunta «¿y si lo divido?» y Trafica muestra la división —
   un Lector de solo lectura y un Remitente con aprobación — con veredictos nuevos para
   cada mitad.

Toda la conversación funciona en cinco idiomas: inglés, japonés, chino,
hindi y español.

## La idea: la trifecta letal

Un agente se vuelve peligroso cuando tres poderes se reúnen en un mismo lugar:

1. **Lee datos privados** (tu correo, archivos, calendario…)
2. **Lee contenido no confiable** (cuerpos de mensajes, páginas web, archivos subidos — lugares
   donde un atacante puede plantar instrucciones)
3. **Puede enviar datos hacia fuera** (enviar correos, publicar mensajes, llamar a API externas)

Con los tres, un solo mensaje envenenado puede convencer al agente para que filtre
tus datos: el patrón que Simon Willison llamó la *lethal trifecta*. La
«Agents Rule of Two» de Meta plantea lo mismo desde el lado de la plataforma: mantén como
máximo dos de los tres en una sesión.

Trifecta Checker califica un perfil de agente:

| Verdict | Significado |
|---|---|
| **Lethal** | Los tres elementos están presentes |
| **Risky** | Dos elementos, o un elemento más un amplificador de riesgo |
| **Low** | Un elemento o menos, sin amplificadores |

Amplificadores: actuar **sin aprobación humana**, **ejecutar código automáticamente**, y
**escribir en la memoria a largo plazo**.

## Cómo funciona

```
description ──▶ extraction ──▶ rule engine ──▶ explanation
               (Muse Spark)    (deterministic)  (Muse Spark)
```

- **El veredicto nunca proviene de un LLM.** Un pequeño motor de reglas determinista
  (`trifecta_checker.py`) aplica las reglas de calificación, de modo que el mismo perfil
  siempre recibe el mismo veredicto. Esa reproducibilidad es lo esencial.
- **El trabajo de Muse Spark es la traducción**: convertir una descripción en texto libre en
  el perfil estructurado del motor, convertir el veredicto de nuevo a lenguaje
  sencillo en cinco idiomas con un escenario de ataque concreto y una solución,
  y mantener la conversación de seguimiento después del veredicto.
- **La extracción está validada.** El motor tiene un vocabulario cerrado. Si el
  modelo inventa un token, la salida se devuelve una vez con el vocabulario
  permitido (una *llamada de reparación*); si sigue sin encajar, la extracción falla
  de forma visible en lugar de adivinar. Los aspectos que la descripción deja abiertos se
  comunican, y la interfaz pregunta sobre el que podría cambiar el
  veredicto.

Cada veredicto incluye su evidencia (qué capacidad produjo qué
elemento) y una **propuesta de separación**: dividir en un Lector de solo lectura y un
Remitente que solo envía texto aprobado por humanos a una lista de permitidos. Las muestras
incluyen el estado «posterior», para que puedas repetir la comprobación y ver cómo una configuración
Lethal se convierte en dos mitades más seguras.

## Inicio rápido

```bash
# The engine alone — no API key needed
python3 trifecta_checker.py
python3 tests/test_engine.py   # reproducibility + boundary tests (8 cases, no LLM)

# Full pipeline (needs access to the Meta Model API)
python3 extract.py --file fixtures/case_c.txt     # description -> verdict
python3 check.py   --file fixtures/case_c.txt --lang en

# Web UI (stdlib only)
python3 app.py 8765   # http://127.0.0.1:8765/
```

## Muestras

| Caso | Configuración | Esperado |
|---|---|---|
| A `case_a.txt` | Resumidor local de notas, sin red | Low |
| B `case_b.txt` | Lee correo + web, no puede enviar | Risky |
| C `case_c.txt` | Agente de correo que envía por su cuenta y ejecuta scripts | Lethal |
| D `case_d.txt` | Asistente cotidiano que envía mensajes de chat | Lethal |
| C-fixed `case_c_fixed_reader.txt` | Después de la división: el Lector | Risky |
| C-fixed `case_c_fixed_sender.txt` | Después de la división: el Remitente aprobado | Low |

Consulta `fixtures/fixtures.json` para ver el manifiesto.

## Limitaciones honestas

- La calificación es una **heurística**, no un estándar. Aún no existe una fórmula de puntuación validada
  para configuraciones de agentes; el conteo de la trifecta es una comprobación
  necesaria, no suficiente.
- El patrón de la trifecta trata principalmente del **robo de datos**. Los agentes pueden ser inseguros
  de otras maneras (herramientas defectuosas, entornos aislados débiles, aprobaciones demasiado amplias) que esta
  comprobación no cubre — consulta el OWASP Top 10 for Agentic Applications para
  ver el panorama más amplio.
- La calidad de la extracción depende de la descripción. Las descripciones vagas producen
  perfiles vagos; el verificador pregunta sobre las lagunas que importan, pero una
  descripción honesta y específica sigue dando el veredicto más fiable.

## Referencias

- Simon Willison, *The lethal trifecta for AI agents* (2025-06-16) —
  https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/
- Meta, *Agents Rule of Two* (2025-10-31) —
  https://ai.meta.com/blog/practical-ai-agent-security/
- OWASP, *Top 10 for Agentic Applications for 2026* —
  https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/

## Construido con

- **Muse Spark** (Meta Model API) para la extracción y la explicación
- Un motor de reglas determinista en Python (este repositorio, escrito durante el evento)
- Trabajo previo del mismo autor, citado como contexto: `ai-governance-control`
  (gobernanza para el entorno de *desarrollo* — puertas de aprobación y
  diseño de fallo cerrado). Trifecta Checker es el lado complementario en tiempo de ejecución:
  diagnostica una configuración de agente que ya existe.
