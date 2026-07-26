# Plan de trabajo — Asistente Jurídico RAG Local

**Última actualización:** 2026-07-25

## Objetivo general

Construir un asistente jurídico local que apoye el análisis de información
documental con fuentes trazables. El sistema no es un decisor jurídico: toda
conclusión requiere revisión y criterio de un profesional competente.

## Principios de trabajo

- Ejecución local y privacidad documental.
- Fuentes trazables y revisión profesional obligatoria.
- Carga diferida de modelos para no consumir recursos al iniciar la aplicación.
- Separación entre conocimiento, recuperación y generación.
- No registrar información sensible en logs.
- No usar APIs externas de inferencia ni OpenAI, Gemini, Ollama o LM Studio en
  la aplicación.
- No subir a Git modelos, documentos, bases de datos ni logs.
- No registrar prompts, respuestas, chunks o documentos completos.
- No avanzar de fase sin cumplir sus criterios de aceptación.
- No realizar operaciones Git automáticamente.
- Mantener `Log.py` y los imports desde `app.core.Log` como mecanismo de
  logging centralizado.

## Arquitectura resumida

- Backend: FastAPI.
- Frontend: React, TypeScript y Vite.
- Persistencia documental: SQLite; recuperación textual FTS5 completada.
- Índice semántico ChromaDB local validado y completado; recuperación híbrida RRF completada.
- Modelo generativo local: Qwen3-1.7B Q4_K_M en GGUF mediante
  `llama-cpp-python`.
- Embeddings locales completados: `multilingual-e5-small`, reutilizados por el
  índice semántico reconstruible.
- Extracción documental con PyMuPDF completada.
- Red jurídica y visualización futuras: NetworkX y PyVis.

## Fases

| Nº | Nombre | Objetivo | Estado | Dependencias | Criterio de aceptación |
| --- | --- | --- | --- | --- | --- |
| 0 | Estructura inicial | Proveer base web, configuración, salud y observabilidad. | Completada | FastAPI, React, TypeScript, Vite | `/api/health`, logging centralizado, pruebas y analizadores disponibles. |
| 1 | Modelo generativo local | Gestionar, verificar y probar Qwen3 local bajo demanda. | Completada | GGUF Qwen3, `llama-cpp-python`, Hugging Face solo para descarga | Archivo verificado, carga diferida, estado seguro e inferencia conversacional controlada. |
| 2 | Persistencia y registro documental | Registrar metadatos y archivos PDF de forma controlada. | Completada | Fase 0 | Metadatos, carga PDF segura, hash, duplicados y borrado lógico; sin extracción de texto, páginas ni chunks. |
| 3 | Extracción, páginas y chunks | Extraer contenido y segmentarlo con trazabilidad documental. | Completada | Fase 2, PyMuPDF | Páginas y chunks persistidos con referencia a documento y página. |
| 4 | Embeddings | Instalar y gestionar `multilingual-e5-small` localmente. | Completada | Fase 3, Sentence Transformers | Embeddings reproducibles sin servicios externos. |
| 5 | Búsqueda textual | Implementar recuperación léxica con SQLite FTS5. | Completada | Fase 2 y Fase 3 | Consultas textuales trazables y cubiertas por pruebas. |
| 6 | Búsqueda semántica | Crear el índice semántico local reconstruible. | Completada | Fase 4, ChromaDB | Recuperación semántica local evaluada. |
| 7 | Recuperación híbrida | Combinar resultados textuales y semánticos. | Completada | Fase 5 y Fase 6 | Ranking híbrido medible y trazable. |
| 8 | Chat RAG | Construir contexto recuperado y respuestas locales asistidas. | Completada | Fase 1 y Fase 7 | Respuestas basadas en recuperación, sin historial no autorizado. |
| 9 | Citas y trazabilidad | Presentar fuentes, documentos y páginas que sustentan la respuesta. | Completada | Fase 3 y Fase 8 | Cada respuesta RAG muestra referencias estructurales verificables y revalidadas. |
| 10 | Matriz HPN | Modelar relaciones entre hechos, pruebas y normas. | Completada | Fase 2 y Fase 9 | Relaciones revisables por el profesional. |
| 11 | Red jurídica | Construir y visualizar relaciones jurídicas. | Pendiente | Fase 10, NetworkX, PyVis | Red local trazable sin decisiones automáticas. |
| 12 | Simulación | Explorar escenarios preliminares sobre la red jurídica. | Pendiente | Fase 11 | Resultados explicables y sujetos a revisión profesional. |
| 13 | OCR | Incorporar reconocimiento óptico para documentos que lo requieran. | Pendiente | Fase 3 | Flujo OCR controlado, medido y trazable. |
| 14 | Búsqueda web controlada | Añadir fuentes web bajo controles explícitos. | Pendiente | Fase 9 | Origen, fecha y trazabilidad de cada fuente externa. |
| 15 | Evaluación y posible especialización | Evaluar el sistema y decidir si procede una especialización futura. | Pendiente | Fases funcionales anteriores | Métricas, evaluación humana y decisión documentada. |

## Estado confirmado

La Fase 0 está completada: backend FastAPI, frontend React, `/api/health`,
middleware con `request_id`, logging mediante `app.core.Log` y validaciones de
pruebas, Ruff, mypy, lint y build.

La Fase 1 está completada: Qwen3-1.7B Q4_K_M está disponible en
`models/llm/qwen3-1.7b/Qwen3-1.7B-Q4_K_M.gguf`, con tamaño verificado de
1.282.439.264 bytes. Se verificaron nombre, extensión, tamaño, ruta y cabecera
GGUF; el modelo se carga de forma diferida, usa `create_chat_completion()` y
la plantilla de chat del GGUF, se libera tras la prueba y no utiliza APIs
externas de inferencia. La prueba controlada respondió `MODELO LOCAL
FUNCIONANDO`; los tiempos observados fueron aproximadamente 1,16 s de carga y
0,85 s de generación. El SHA-256 oficial permanece pendiente de fijarse en el
manifiesto.

## Delimitación de las fases 2 y 3

### Fase 2 — Persistencia y registro documental

- Persistencia mediante SQLite.
- Definición del esquema de datos y repositorios.
- Registro y almacenamiento controlado de archivos.
- Cálculo de hash SHA-256 y detección de duplicados.
- Estados de procesamiento.
- Sin extracción de texto, páginas o chunks.
- Dependencia técnica: Fase 0.

### Fase 3 — Extracción y segmentación documental

- Extracción con PyMuPDF.
- Persistencia de páginas.
- Segmentación y persistencia de chunks.
- Trazabilidad por documento y página.

## Fase 8 — Chat RAG local

La Fase 8 está **Completada**. `POST /api/chat/rag` reutiliza la recuperación híbrida, lee el
texto vigente desde SQLite, selecciona chunks en orden mediante un presupuesto
estricto calculado con el tokenizer de Qwen y genera con el modelo local ya
cargado. Los documentos se serializan como evidencia no confiable y nunca como
roles o instrucciones.

El flujo es stateless, no carga modelos ni reconstruye índices automáticamente
y responde sin generación cuando no hay contexto suficiente. No incluye citas
finales, reranking, historial persistente, streaming ni cambios de frontend.

## Cierre documental de la Fase 8

La validación integral real confirmó Chat RAG local y stateless mediante
`POST /api/chat/rag`, recuperación híbrida FTS5 + ChromaDB y una única
invocación de `HybridSearchService` por petición. SQLite permanece como fuente
de verdad; el texto vigente se obtiene desde SQLite, los candidatos se
revalidan y deduplican por `chunk_id`, y los snippets no se usan como contexto.
La selección fue determinista y respetó límites de chunks y tokens.

Se validaron el tokenizer GGUF y la plantilla conversacional de Qwen cuando
está disponible, el margen conservador de mensajes y la condición
`prompt_tokens + max_new_tokens + safety_margin <= context_size`, con
`context_size=4096`, `max_new_tokens=512`, `safety_margin=128`,
`context_tokens=1728` y `prompt_tokens <= 3456`. La evidencia se trató como no
confiable, con un mensaje system fijo y uno user, `/no_think` controlado y
neutralización de roles y delimitadores.

La generación local se ejecutó fuera del event loop, con lock controlado,
salida sin bloques de razonamiento ni HTML ejecutable, sin historial,
streaming ni APIs externas. Se validaron HTTP 200 `answered`, tres chunks de
contexto, el caso `insufficient_context` sin invocar Qwen, persistencia tras
reinicio sin rebuild y respuestas públicas sin datos internos. `requires_professional_review`
permanece siempre en `true`.

Los conteos SQLite iniciales y finales permanecieron en 1 documento, 28
páginas, 44 chunks y 44 registros FTS5. Qwen y embeddings terminaron
`unloaded`, los archivos locales permanecieron disponibles, Uvicorn se cerró,
el puerto quedó libre y no quedaron procesos, handles ni tareas propias.
El validador fue aprobado con código 0: 281 pruebas, Ruff sin errores y mypy
sin errores en 76 archivos.

## Cierre de la Fase 9 — Citas y trazabilidad estructural

La Fase 9 está **Completada** tras la validación integral real. Los chunks realmente incluidos en el contexto reciben
marcadores efímeros y deterministas `[F1]..[Fn]`. La salida se valida con un
parser cerrado, cobertura por elemento sustantivo y una nueva lectura de
SQLite posterior a la generación. La metadata pública proviene siempre de
SQLite y no del modelo.

`POST /api/chat/rag` conserva su contrato y añade `citation_count` y
`citations`. Las referencias identifican documento, tipo, chunk y páginas,
sin exponer texto, rutas, hashes, scores ni identificadores internos de chunk.
La trazabilidad confirma qué fuente del contexto fue citada; no demuestra por
sí sola veracidad jurídica, entailment completo ni suficiencia semántica.

La validación integral real fue aprobada con código 0: 443 pruebas, Ruff sin
errores y mypy sin errores en 77 archivos. Se validaron Chat RAG HTTP 200,
correspondencia exacta, revalidación SQLite, `insufficient_context` sin Qwen,
persistencia tras reinicio, privacidad y conteos SQLite sin cambios (1 / 28 /
44 / 44). Ambos modelos terminaron `unloaded` y no quedaron procesos propios.

## Fase 10 — Matriz HPN manual y revisable

La implementación permite registrar matrices, hechos, pruebas, normas,
fuentes documentales y relaciones dirigidas. Los elementos se introducen y
revisan manualmente; el sistema no determina hechos probados, normas aplicables,
fuerza probatoria ni decisiones jurídicas.

SQLite conserva matrices, nodos, snapshots mínimos de fuentes y relaciones.
Las fuentes se resuelven por documento y número de chunk, se identifican
internamente por `chunk_id` y se comparan mediante un fingerprint SHA-256 no
reversible. Su estado público es `valid`, `stale` o `unavailable`; una lectura
no actualiza ni sustituye automáticamente la snapshot.

La Fase 10 queda **Completada** tras la validación funcional integral HPN y la
comprobación objetiva de procesos, listeners, archivos temporales, sidecars,
persistencia, reinicio e integridad de la base original. La instrumentación del
centinela de disposición es diagnóstica y no bloqueante.
El estado `archived` es de solo lectura y distinto del borrado lógico. Una
fuente obsoleta no modifica automáticamente la revisión humana del nodo, pero
impide que la matriz cumpla `valid_for_review`.

## Próximo paso autorizado

Fase 11 — Red jurídica con NetworkX y PyVis. La Fase 11 permanece pendiente y
no forma parte de esta implementación.
