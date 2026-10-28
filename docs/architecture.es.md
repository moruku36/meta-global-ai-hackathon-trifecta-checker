# Trifecta Checker — Diseño general

[English](architecture.md) · [日本語](architecture.ja.md) · [中文](architecture.zh.md) · [हिन्दी](architecture.hi.md) · **Español**

Estado: tal como se construyó y desplegó, 2026-10-28.
Demostración en vivo: https://meta-global-ai-hackathon-trifecta-c.vercel.app/
Repositorio: https://github.com/moruku36/meta-global-ai-hackathon-trifecta-checker

## 1. Propósito

Una revisión de seguridad previa al despegue para agentes de IA, dirigida a personas no especialistas. La persona usuaria
describe con sus propias palabras lo que su agente puede hacer; el verificador evalúa
si esa combinación de poderes constituye la «trifecta letal» (Simon
Willison) — acceso a datos privados × exposición a contenido no confiable × comunicación
externa — y explica el resultado en lenguaje sencillo, con una solución
concreta (dividir el agente, controlar el envío).

Posicionamiento: diagnóstico en la fase de diseño. Complementa las herramientas de cumplimiento
en tiempo de ejecución (p. ej., NVIDIA OpenShell) y el trabajo previo del autor
`ai-governance-control` (gobernanza para el entorno de *desarrollo*).
La «Agents Rule of Two» de Meta es el referente publicado más cercano a la
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

Sin base de datos, sin paso de compilación, sin sesión en el servidor: el cliente conserva el
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
    token produjo qué elemento) y una propuesta de separación (Reader
    de solo lectura + Sender con aprobación y lista de permitidos).
- **`extract.py` — extracción con Spark con barreras de seguridad.** Texto libre → perfil
  JSON limitado al vocabulario cerrado. Los tokens no válidos activan UNA
  llamada de reparación que muestra al modelo el vocabulario permitido; si la salida
  sigue sin encajar, la extracción falla de forma visible (sin adivinar). El resultado
  también enumera los aspectos `unclear` — un subconjunto depurado de {reads_private,
  reads_untrusted, sends_out, human_approval} — que indica lo que la
  descripción deja sin aclarar.
- **`explain.py` — del veredicto a una explicación amable.** Encabezados fijos en
  cinco idiomas (en/ja/zh/hi/es): Verdict / What could happen / How to
  fix it / Bottom line / Next steps. Tono cálido, con palabras cotidianas; los «Next
  steps» son sugerencias amables que terminan con UNA pregunta de invitación.
- **`check.py` — canalización + conversación de seguimiento.** Divide el flujo en
  `extract_and_judge` (1 llamada al LLM), `judge_profile` (0 llamadas),
  `explain_result` (1 llamada, el fallo no es fatal) y `followup` (Spark
  responde en el idioma de la interfaz, solo con palabras sencillas, nunca tokens sin procesar; el
  modelo puede terminar con `[[SPLIT]]` para activar la vista dividida, o responder
  `[[NEW]]` cuando la persona usuaria describe un agente diferente).
- **`llm.py` — llamador compartido de Spark.** Alojado: variable de entorno `META_API_KEY` →
  llamada directa a api.meta.ai. Desarrollo local: recurre a una clave guardada en bóveda
  mediante un subproceso auxiliar (la clave nunca aparece en el código ni en los registros).
- **`app.py` — el generador del cliente web.** Una sola página HTML estática: interfaz
  solo de chat con una mascota (Trafica), selector de idioma que controla toda la interfaz,
  entrada de voz (Web Speech API), adjunto de archivos, y la lógica de repregunta
  descrita abajo. Adjuntar un JSON de configuración de MCP (p. ej., una configuración de cliente
  Claude Desktop / MCP) se resume en el lado del cliente en una descripción sencilla
  de sus servidores, que luego pasa por la extracción
  normal — así se puede revisar tal cual una configuración real de agente
  (`fixtures/sample_mcp_config.json`). El pie de página incluye la
  advertencia de que se trata de una heurística y un aviso de privacidad sobre que la demostración funciona
  con créditos de socios.

## 4. Diseño de la conversación

1. **Saludo.** Trafica se presenta: qué revisa y cómo
   empezar (con una frase de ejemplo). Se vuelve a mostrar en el idioma elegido
   hasta que comienza la conversación.
2. **El veredicto primero, en palabras.** La burbuja del veredicto empieza con una frase
   hablada («Lo revisé — el veredicto es Risky»), luego la insignia,
   chips amables de los elementos y un recuento de «n de 3 poderes».
3. **Repregunta, como máximo UNA pregunta.** El cliente refleja la regla del motor
   localmente y pregunta solo cuando un aspecto `unclear` podría cambiar realmente
   el veredicto. Las respuestas son chips de Yes / No / Not sure (también se puede escribir).
   Responder aplica una edición representativa y vuelve a evaluar mediante
   /api/check-profile. Escribir en lugar de elegir interrumpe la pregunta y
   vuelve a extraer a partir del texto combinado.
4. **Conversación después del veredicto.** Los seguimientos van a Spark mediante
   /api/followup; «what if I split it?» muestra las mitades Reader/Sender
   con veredictos nuevos — el arco de demostración Lethal → Risky + Low.

## 5. Decisiones clave y compensaciones

- **Determinismo antes que ingenio.** La calificación es reproducible: mismo
  perfil, mismo veredicto. El LLM se trata como un traductor, nunca como
  juez. Esta es la principal garantía de confianza del producto.
- **Fallo visible antes que suposición silenciosa** en la extracción (una reparación, luego
  fallo visible).
- **Alojamiento sin estado.** Nivel gratuito de Vercel, Python solo con stdlib; no se almacena ningún dato de
  usuario en ninguna parte. Las descripciones solo se envían a Meta Model API.
- **Protecciones de la API de la demostración pública.** Los cuatro endpoints comparten `api_guard.py`:
  límites estrictos del tamaño del cuerpo de la solicitud (64 KB) y de la longitud del texto por campo,
  aplicados antes de cualquier llamada al LLM, además de un límite de frecuencia por IP aproximado
  (contador en proceso — las instancias sin estado hacen que frene bucles ingenuos
  en lugar de garantizar un límite global; un límite estricto requeriría un
  almacén compartido como Vercel KV). Añadido el 2026-10-28 antes de abrir la
  demostración a UAT pública.
- **Advertencia de créditos gratuitos.** Mientras se usen los créditos gratuitos de socios, el contenido
  enviado puede usarse para mejorar el producto — se espera que el público de la interfaz
  pruebe con descripciones de ejemplo, y esto se indica para la UAT.
- **Honestidad sobre el alcance.** La calificación es una heurística, no un estándar; la
  trifecta cubre principalmente el robo de datos, no todos los riesgos de los agentes (se hace referencia al Top 10
  Agentic de OWASP para el mapa más amplio).

## 6. Verificación

- **Reproducibilidad del motor (sin LLM):** `test_engine.py` evalúa los seis
  perfiles canónicos más dos casos límite (un elemento + amplificador;
  sin poderes), cada uno dos veces — 8/8 superados, veredictos idénticos byte por byte entre ejecuciones.
- **Extracción:** verificada 4/4 en los textos de prueba (Low / Risky /
  Lethal / Lethal) frente a los veredictos esperados del motor. Una prueba de la ruta de
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
  (ajustes de asistentes, configuraciones de frameworks de agentes) aún no se analizan.
- Aún no hay tarjeta de veredicto compartible / vista de equipo.
- La entrada de voz depende de la compatibilidad del navegador con SpeechRecognition.
- Idiomas más allá de los cinco actuales quedan para trabajo futuro.

## 8. Correspondencia con los criterios del hackathon (autoevaluación)

- **Impacto (30%)**: dirigido a la creciente población de constructores de agentes no especialistas;
  una revisión de 30 segundos antes de conectar un agente.
- **Herramientas de Meta (25%)**: construido sobre Muse Spark vía Meta Model API para
  extracción, explicación y conversación; el diseño mantiene una ruta de pesos abiertos
  (Muse Spark Open verificado para extracción/explicación en las pruebas).
- **Profundidad técnica (20%)**: motor determinista + extracción validada
  con reparación, lógica de repregunta que cambia el veredicto, protocolo de acciones para
  seguimientos.
- **Demostración (25%)**: arco de 3 minutos — agente de correo Lethal → repregunta → división
  en Risky + Low → voz + interfaz en japonés.
