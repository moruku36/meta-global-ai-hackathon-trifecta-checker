# Trifecta Checker — Diseño general

[English](architecture.md) · [日本語](architecture.ja.md) · [中文](architecture.zh.md) · [हिन्दी](architecture.hi.md) · **Español**

Estado: tal como se construyó y desplegó, 2026-10-28.
Demo en vivo: https://meta-global-ai-hackathon-trifecta-c.vercel.app/
Repo: https://github.com/moruku36/meta-global-ai-hackathon-trifecta-checker

## 1. Propósito

Una revisión de seguridad previa al vuelo para agentes de IA, dirigida a personas no especialistas. La persona usuaria
describe lo que su agente puede hacer, con sus propias palabras; el verificador califica
si esa combinación de poderes es la "lethal trifecta" (Simon
Willison) — acceso a datos privados × exposición a contenido no confiable × comunicación
externa — y explica el resultado en lenguaje sencillo, con una solución
concreta (dividir el agente, controlar el envío).

Posicionamiento: diagnóstico en el momento del diseño. Complementa las herramientas de cumplimiento
en tiempo de ejecución (p. ej., NVIDIA OpenShell) y el trabajo previo del autor
`ai-governance-control` (gobernanza para el entorno de *desarrollo*).
La "Agents Rule of Two" de Meta es el referente publicado más cercano a la
lógica de calificación.

## 2. Arquitectura

```
Browser (single static page, chat UI)
   │  HTTPS / JSON
   ▼
Vercel serverless functions (Python, stdlib only)
   ├── POST /api/check          text ─▶ profile + verdict (+ unclear list)
   ├── POST /api/check-profile  profile ─▶ verdict        (0 LLM calls)
   ├── POST /api/explain        verdict ─▶ plain-language explanation
   └── POST /api/followup       message ─▶ conversational reply (+ action)
   │
   ▼
Meta Model API — Muse Spark 1.3 (api.meta.ai, OpenAI-compatible)
   used ONLY for: extraction, explanation, follow-up conversation
```

Sin base de datos, sin paso de compilación, sin sesión en el servidor: el cliente lleva el
perfil/veredicto actual en el estado de la página y lo reenvía con cada llamada.

## 3. Componentes

- **`trifecta_checker.py` — motor de reglas determinista.** El veredicto nunca
  proviene de un LLM. Vocabulario cerrado de capacidades:
  - DATA_ACCESS {gmail_read, email_read, calendar_read, local_files,
    drive_read, contacts_read, message_read}
  - UNTRUSTED {web_browse, email_body, uploaded_files, webhook, chat_input}
  - OUTBOUND {email_send, chat_post, http_post, message_send,
    code_execute_outbound}
  - AMPLIFIERS {no_human_approval, auto_execute_code,
    long_term_memory_write}
  - Regla: 3 elementos = **Lethal**; 2 elementos, o 1 + amplificador =
    **Risky**; en los demás casos **Low**. Cada veredicto incluye evidencia (qué
    token produjo qué elemento) y una propuesta de separación (Lector
    de solo lectura + Emisor con aprobación y lista de permitidos).
- **`extract.py` — extracción con Spark con barreras de seguridad.** Texto libre → perfil
  JSON restringido al vocabulario cerrado. Los tokens no válidos activan UNA
  llamada de reparación que muestra al modelo el vocabulario permitido; si la salida
  sigue sin encajar, la extracción falla de forma visible (sin adivinar). El resultado
  también enumera los aspectos `unclear` — un subconjunto depurado de {reads_private,
  reads_untrusted, sends_out, human_approval} — que nombra lo que la
  descripción deja abierto.
- **`explain.py` — del veredicto a una explicación amable.** Encabezados fijos en
  cinco idiomas (en/ja/zh/hi/es): Verdict / What could happen / How to
  fix it / Bottom line / Next steps. Tono cálido, con palabras cotidianas; los "Next
  steps" son sugerencias amables que terminan con UNA pregunta acogedora.
- **`check.py` — flujo + conversación de seguimiento.** Divide el flujo en
  `extract_and_judge` (1 llamada al LLM), `judge_profile` (0 llamadas),
  `explain_result` (1 llamada, fallo no fatal) y `followup` (Spark
  responde en el idioma de la interfaz, solo con palabras sencillas, nunca tokens crudos; el
  modelo puede terminar con `[[SPLIT]]` para activar la vista dividida, o responder
  `[[NEW]]` cuando la persona usuaria describe un agente diferente).
- **`llm.py` — llamador compartido de Spark.** Alojado: variable de entorno `META_API_KEY` →
  llamada directa a api.meta.ai. Desarrollo local: recurre a una clave guardada en bóveda
  mediante un subproceso auxiliar (la clave nunca aparece en el código ni en los registros).
- **`app.py` — el generador del cliente web.** Una sola página HTML estática: interfaz
  solo de chat con una mascota (Trafica), selector de idioma que controla toda la interfaz,
  entrada de voz (Web Speech API), adjunto de archivos, y la lógica de repregunta
  descrita abajo. Adjuntar un JSON de configuración de MCP (p. ej., una config de cliente
  Claude Desktop / MCP) se resume en el lado del cliente en una descripción sencilla
  de sus servidores, que luego pasa por la extracción
  normal — así se puede revisar una configuración de agente real tal cual
  (`fixtures/sample_mcp_config.json`). El pie de página lleva el
  aviso de que es una heurística y una nota de privacidad sobre que la demo funciona
  con créditos de socios.

## 4. Diseño de la conversación

1. **Saludo.** Trafica se presenta: qué revisa y cómo
   empezar (con una frase de ejemplo). Se vuelve a mostrar en el idioma elegido
   hasta que empieza la conversación.
2. **El veredicto primero en palabras.** La burbuja del veredicto empieza con una frase
   hablada ("Le eché un vistazo — el veredicto es Risky"), luego la insignia,
   chips amables de elementos y un recuento de "n de 3 poderes".
3. **Repregunta, como máximo UNA pregunta.** El cliente replica la regla del motor
   localmente y pregunta solo cuando un aspecto `unclear` podría cambiar realmente
   el veredicto. Las respuestas son chips de Sí / No / No estoy seguro (también se puede escribir).
   Responder aplica una edición representativa y recalifica mediante
   /api/check-profile. Escribir en lugar de pulsar interrumpe la pregunta y
   vuelve a extraer a partir del texto combinado.
4. **Conversación después del veredicto.** Los seguimientos van a Spark mediante
   /api/followup; "¿y si lo divido?" muestra las mitades Lector/Emisor
   con veredictos nuevos — el arco de la demo Lethal → Risky + Low.

## 5. Decisiones clave y concesiones

- **Determinismo antes que ingenio.** La calificación es reproducible: mismo
  perfil, mismo veredicto. El LLM se trata como un traductor, nunca como un
  juez. Esta es la principal afirmación de confianza del producto.
- **Fallo visible antes que suposición silenciosa** en la extracción (reparar una vez, luego
  fallar de forma visible).
- **Alojamiento sin estado.** Nivel gratuito de Vercel, Python solo con stdlib; no se
  almacena ningún dato de la persona usuaria en ningún lugar. Las descripciones van solo a Meta Model API.
- **Protecciones de la API de la demo pública.** Los cuatro endpoints comparten `api_guard.py`:
  límites estrictos al tamaño del cuerpo de la solicitud (64 KB) y a la longitud del texto por campo,
  aplicados antes de cualquier llamada al LLM, más un límite de frecuencia por IP de mejor esfuerzo
  (contador en proceso — las instancias sin estado hacen que frene bucles ingenuos
  en lugar de garantizar un límite global; un límite estricto necesitaría un
  almacén compartido como Vercel KV). Añadido el 2026-10-28 antes de abrir la
  demo a UAT pública.
- **Advertencia de créditos gratuitos.** Mientras se usen créditos gratuitos de socios, el contenido
  enviado puede usarse para mejorar el producto — se espera que el público de la interfaz
  pruebe con descripciones de ejemplo, y esto se indica para la UAT.
- **Honestidad sobre el alcance.** La calificación es una heurística, no un estándar; la
  trifecta cubre sobre todo el robo de datos, no todos los riesgos de los agentes (se referencia el Top 10
  Agentic de OWASP para el mapa más amplio).

## 6. Verificación

- **Reproducibilidad del motor (sin LLM):** `tests/test_engine.py` califica los seis
  perfiles canónicos más dos casos límite (un elemento + amplificador;
  sin poderes), cada uno dos veces — 8/8 aprobados, veredictos idénticos a nivel de byte entre ejecuciones.
- **Extracción:** verificada 4/4 en los textos de prueba (Low / Risky /
  Lethal / Lethal) frente a los veredictos esperados del motor. Una sonda de la ruta de
  reparación (una descripción que primero produjo un token inventado) confirmó
  que la llamada de reparación lo normaliza al vocabulario cerrado y aun así
  llega al veredicto correcto; un perfil que no se puede reparar falla
  de forma visible por diseño.
- **Ruta de pesos abiertos:** la extracción y la explicación también se ejecutaron
  de extremo a extremo en Muse Spark Open (`meta-models/muse-spark-open-1026` vía
  Baseten) el 2026-10-27 — la extracción del Caso C devolvió el perfil
  correcto, y las explicaciones se generaron correctamente en japonés e inglés.
- Pruebas de humo en producción después de cada despliegue: /api/check, /api/explain,
  /api/followup.

## 7. Limitaciones y trabajo futuro

- La calidad de la extracción depende de la calidad de la descripción; la repregunta mitiga
  esto pero no lo elimina.
- La importación de configuraciones reales es básica: el JSON de configuración de MCP se resume
  en el lado del cliente (nombres de servidores, comandos, URL). Otros formatos de exportación
  (ajustes de asistentes, configs de frameworks de agentes) aún no se analizan.
- Aún no hay tarjeta de veredicto compartible / vista de equipo.
- La entrada de voz depende de la compatibilidad del navegador con SpeechRecognition.
- Idiomas más allá de los cinco actuales quedan para el futuro.

## 8. Correspondencia con la rúbrica del hackathon (autoevaluación)

- **Impacto (30%)**: se dirige a la creciente población de constructores de agentes
  no especialistas; una revisión de 30 segundos antes de conectar un agente.
- **Herramientas de Meta (25%)**: construido sobre Muse Spark vía Meta Model API para
  extracción, explicación y conversación; el diseño mantiene una ruta de pesos
  abiertos (Muse Spark Open verificado para extracción/explicación en las pruebas).
- **Profundidad técnica (20%)**: motor determinista + extracción validada
  con reparación, lógica de repregunta que cambia el veredicto, protocolo de acciones para
  seguimientos.
- **Demo (25%)**: arco de 3 minutos — agente de correo Lethal → repregunta → división
  en Risky + Low → voz + interfaz en japonés.

## 9. Fundamento del diseño

El patrón anterior — las comprobaciones deterministas toman la decisión, un LLM solo
donde se necesita criterio, la aprobación humana como puerta — sigue el mismo
patrón que el propio taller del hackathon de Meta enseñó para el diseño de agentes:
"Agents 102: Best Practices for Verifiable Agents Pt. 2" (sesión en vivo del Meta Global
AI Developer Hackathon; Yash Khare, ingeniero
socio de Meta).

Tres alineaciones:

- **La verificación está integrada, no es opcional.** La regla del taller:
  la verificación vive dentro de la herramienta, nunca como un paso separado que el
  agente puede omitir. Aquí, el veredicto lo calcula
  `trifecta_checker.py` en cada revisión — ninguna ruta de LLM puede evitarlo ni
  anularlo.
- **Primero determinista, LLM como juez después.** En el taller,
  las comprobaciones de integridad y formato son código puro; el LLM solo juzga
  si una afirmación está realmente respaldada. Aquí, el motor de reglas es dueño
  del veredicto; Muse Spark solo extrae el perfil y explica el
  resultado en lenguaje sencillo.
- **La aprobación humana es una puerta.** El taller termina en una aprobación humana
  incluso después de que pasen todas las comprobaciones. Aquí, actuar sin aprobación humana
  (`no_human_approval`) es un amplificador de riesgo en la propia calificación.

La demo del taller también es un ejemplo aleccionador: el memorando construido en
la sesión anterior no pasó la verificación — afirmaciones sin respaldo y una
regla rota. La salida no verificada de un agente trae errores. Trifecta Checker
aplica la misma lección un paso antes: revisar la configuración
antes de que el agente se ejecute, no solo la salida después.
