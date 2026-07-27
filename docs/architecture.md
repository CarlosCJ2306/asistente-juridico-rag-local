# Arquitectura

## Visión general

El sistema es local. FastAPI expone servicios documentales, recuperación, Chat RAG, Matrices HPN y Red jurídica. React/Vite consume esos contratos mediante un cliente HTTP compartido. SQLite es la fuente de verdad; FTS5 y ChromaDB son índices derivados y reconstruibles.

## Backend y persistencia

- `documents`, `document_pages` y `document_chunks` almacenan metadatos, páginas y fragmentos trazables.
- `documents` distingue capa de conocimiento, procedencia, revisión editorial,
  vigencia jurídica y estado de indexación, y permite enlazar una versión con
  el documento que sustituye. Estos ejes no se mezclan con el estado técnico
  de extracción.
- El servicio documental valida PDF, escribe temporalmente, evita traversal y registra metadatos de forma controlada.
- PyMuPDF reconstruye texto por palabras y líneas; el limpiador y el chunker conservan orden y rangos de página.
- Alembic mantiene el esquema explícitamente. FastAPI no crea tablas ni ejecuta migraciones al iniciar.

`DocumentGovernanceService` centraliza las matrices de transición de revisión,
vigencia e indexación, las reglas de capa y versionado, y la elegibilidad RAG
calculada. Cada flujo de recuperación obtiene candidatos desde el índice,
carga chunks y gobernanza vigente desde SQLite y aplica esa política antes de
exponer resultados. La evaluación usa campos ya cargados, no persiste la
elegibilidad y evita consultas N+1.

## Recuperación e IA local

- FTS5 indexa texto de chunks y se sincroniza con triggers SQLite.
- `multilingual-e5-small` genera embeddings locales bajo demanda.
- ChromaDB persiste solo embeddings y metadatos mínimos, incluida la capa; no reemplaza los chunks SQLite.
- El fingerprint semántico incluye los cambios de gobernanza que alteran la
  fuente y la versión del esquema de metadata. Una incompatibilidad exige
  rebuild explícito mediante colección temporal y activación atómica.
- La búsqueda híbrida combina únicamente candidatos elegibles de FTS5 y
  semántica mediante RRF, con filtros de capa y revalidación contra SQLite.
- Qwen3 GGUF se ejecuta mediante `llama-cpp-python`, con plantilla conversacional del GGUF y carga explícita.

## RAG y citas

`RagChatService` recupera una vez, obtiene texto vigente desde SQLite y vuelve
a comprobar elegibilidad y filtros antes de seleccionar contexto. Si no queda
evidencia elegible, no genera una respuesta jurídica. `RagCitationService`
valida markers, cobertura y nuevamente la fuente gobernada antes de construir
citas con nombre visible, capa, documento, chunk y páginas. El Chat es
stateless y exige revisión profesional.

## Matrices HPN y Red jurídica

Las matrices almacenan nodos fact, evidence y norm, sus fuentes y relaciones dirigidas revisables. NetworkX construye una proyección de solo lectura; la API JSON ofrece DTOs sanitizados y PyVis exporta una visualización local restringida. Las métricas y relaciones son estructurales, no conclusiones jurídicas.

## Frontend y proxy

React, TypeScript y Vite implementan App Shell, Design System, cliente HTTP compartido, Inicio, Matrices HPN y Red jurídica. En desarrollo, `frontend/.env` define la base local y Vite redirige `/api` al backend. El iframe PyVis usa ruta relativa y sandbox restringido; React no interpreta HTML HPN.

## Estado de conexión

| Área | Estado |
| --- | --- |
| Flujo documental y Chat RAG backend | Implementado y conectado |
| Biblioteca, carga, procesamiento, corpus, chat y fuentes frontend | Pendiente |
| Matrices HPN frontend | Implementado |
| Red jurídica frontend | Implementada; validación integrada pendiente |
| Fuentes web y propuestas HPN asistidas | Futuro |

## Seguridad y logging

Los módulos usan `app.core.Log` y registran solo metadatos operativos. No se registran prompts, respuestas ni texto documental. La política de privacidad está en [security-privacy.md](security-privacy.md) y el detalle técnico de logging en [logging.md](logging.md).
