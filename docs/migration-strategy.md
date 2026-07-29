# Estrategia de migración hacia inteligencia de casos

## Principios

La migración es aditiva, reversible por bloque y sin reinterpretar datos.
SQLite continúa como fuente de verdad; FTS5, ChromaDB, NetworkX y PyVis
permanecen derivados.

## Secuencia

### 12D — Reestructuración del producto

12D-0 definió límites, navegación, política de deprecación y harnesses. 12D-1
implementó fachadas, contratos, ports y adaptadores inactivos con paridad de
rutas. 12D-2 incorporó navegación y shell estático sin crear persistencia de
casos. 12D-3 formalizó compatibilidad y deprecación antes de cualquier retiro.
No se alteraron rutas HPN/Red ni datos existentes.

### 12E — Dominio de casos y expediente

12E-1 creó `Case`, retención, ownership, auditoría base y `/api/cases` mediante
la revisión `20260728_09`. 12E-2 añadió `CaseDocument` mediante
`20260729_10`, también sin backfill ni reinterpretación. El workspace frontend
seguirá en 12E-3.
El backfill solo podrá afectar recursos que un usuario vincule explícitamente.

### 12F — Extracción estructurada de caso

Incorporar entidades y artefactos de extracción versionados sobre servicios documentales existentes.

### 12G — HPN de caso

Versionar matrices, revisión y fuentes dentro del expediente. Conservar HPN global durante la transición.

### 12H — Red jurídica de caso

Reutilizar NetworkX/PyVis sobre una versión HPN seleccionada y trazable.

### 12I — Métricas y simulaciones

Añadir métricas estructurales y escenarios explícitos, sin probabilidades o conclusiones jurídicas automáticas.

### 12J — Dashboard de caso

Componer estados, advertencias, revisiones y artefactos aceptados.

### 12K — Asistente de caso

Separar conversaciones del caso, recuperación acotada y evidencia vigente; conservar el Asistente jurídico general.

### 12L — Evaluación y cierre

Implementar `CaseEvaluationHarness`, casos dorados, regresión, privacidad y validación integral.

La importación web se pospone como capacidad futura de baja prioridad.

## Compatibilidad y deprecación

- No cambiar respuestas existentes de manera incompatible.
- Introducir contratos de caso nuevos y tipados.
- Mantener rutas HPN/Red actuales hasta paridad y asignación explícita.
- Anunciar deprecación antes de redirecciones.
- Conservar una vista legacy para recursos no asignados.
- Eliminar código o tablas solo en una fase posterior con backup, métricas de uso y migración validada.

## Datos e índices

Los documentos no se copian por caso. `case_documents` define la membresía
explícita de documentos privados o temporales existentes, sin modificar su
gobernanza. FTS5 y ChromaDB podrán filtrar por los documentos del caso en un
bloque futuro, pero no guardan la política autoritativa. Los artefactos se
versionan; las proyecciones se regeneran a partir de SQLite.

## Rollback

Cada bloque debe incluir migración temporal probada, backup operativo antes de la base principal y downgrade que preserve datos previos. Si falla un backfill o validación, las rutas existentes siguen operativas y la feature nueva permanece deshabilitada.

## Criterio de retiro

Un módulo legacy solo se retira cuando hay paridad funcional, migración verificada, ausencia de referencias activas, documentación actualizada y validación de privacidad, accesibilidad y recuperación.
