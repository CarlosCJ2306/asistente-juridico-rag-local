# CaseEvaluationHarness

## Estado y propósito

**Diseño planificado.** Es un sistema de regresión técnica para casos sintéticos. No califica la corrección de una decisión jurídica ni sustituye revisión profesional.

12D-3 no activa este harness ni genera casos, fixtures, informes o evaluaciones.

## Aislamiento

- SQLite, storage, FTS5 y ChromaDB temporales.
- Modelos falsos deterministas por defecto; modelos locales reales solo en una validación manual explícita y offline.
- Sin documentos, índices, conversaciones ni modelos principales.
- Informes sanitizados en una carpeta local ignorada.

## Paquete de caso dorado

Cada fixture versionada contiene manifiesto, archivos sintéticos, configuración, resultados esperados por etapa y tolerancias. No contiene datos personales ni expedientes reales. Los golden cases cubren rutas felices, ausencia de fuente, contradicción, duplicados, ciclos, gobernanza y revisión.

## Validaciones

- conformidad de esquemas y versiones;
- determinismo de orden, IDs públicos y fingerprints;
- cobertura de hechos/evidencias/normas;
- fuentes ausentes, stale o unavailable;
- relaciones inválidas, duplicadas o huérfanas;
- diferencias entre versión esperada y obtenida;
- privacidad de API, logs e informes;
- recuperación tras fallo, reintento, cancelación y reinicio;
- estabilidad de métricas estructurales.

## Métricas seguras

Conteos, porcentajes de cobertura estructural, etapas aprobadas, relaciones inválidas, artefactos sin fuente, duplicados, duración y consumo aproximado de recursos. Ninguna métrica se denomina probabilidad de éxito, suficiencia probatoria o certeza jurídica.

## Comparación de versiones

El informe compara `pipeline_version`, `schema_version`, productor y fingerprints. Presenta cambios agregados y códigos; no incluye texto jurídico completo, prompts, vectores, rutas, SQL ni identificadores reales.

## Resultado

Estados `PASS`, `FAIL`, `SKIP` y `BLOCKED`. El código de salida es cero solo si pasan todas las validaciones obligatorias. Una diferencia golden requiere aprobación humana para actualizar la expectativa; el harness nunca la acepta automáticamente.

## Relación con calidad existente

Pytest, Ruff, mypy y validaciones frontend continúan. Los validadores históricos por fase se conservan, pero nuevos escenarios integrales convergerán aquí para evitar duplicación de procesos, cleanup e informes.
