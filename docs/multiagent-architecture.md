# Arquitectura multiagente

## Estado

**Futuro y no implementado.** 12D recomienda primero `CasePipelineHarness`, determinista y controlado. No existe coordinación autónoma de agentes en el producto actual.

12D-3 no incorpora agentes, orquestación ni herramientas nuevas; solo prepara
compatibilidad interna para recursos legacy.

## Razón para posponer

La extracción, HPN, Red, métricas y escenarios requieren entradas tipadas, trazabilidad, revisión y recuperación ante fallos. Agentes autónomos introducirían estado implícito, variabilidad y una superficie de auditoría mayor antes de estabilizar esos contratos.

## Condiciones mínimas de adopción futura

- cada agente implementa una interfaz de etapa existente;
- entradas y salidas cumplen schemas versionados;
- herramientas permitidas por lista cerrada;
- sin Internet ni servicios externos;
- sin memoria oculta compartida;
- presupuesto de tokens, tiempo e intentos;
- checkpoints y auditoría controlados por el harness;
- ninguna decisión jurídica automática;
- gates humanos obligatorios para promoción de artefactos;
- pruebas de prompt injection, aislamiento y reproducibilidad.

## Límites de autoridad

Un agente futuro podrá proponer un artefacto `draft`; no podrá aprobar fuentes, declarar hechos probados, cambiar vigencia, archivar un caso, eliminar evidencia ni promover una revisión. El orquestador valida y persiste; el agente no accede directamente a SQLite, storage o índices.

## Patrón de integración

`CasePipelineHarness -> StageAdapter -> AgentAdapter opcional -> salida tipada -> validación -> artefacto draft`

El fallback siempre será una etapa determinista o una intervención humana, nunca un segundo agente no declarado. La actividad se registra con metadatos operativos y códigos seguros, sin prompts ni razonamiento interno.
