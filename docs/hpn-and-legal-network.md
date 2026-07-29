# HPN y Red jurídica en el dominio de casos

## Convivencia legacy 12D-3

Las matrices HPN y la Red jurídica actuales siguen siendo globales, manuales y
operativas. La clasificación y las referencias de compatibilidad son internas;
no añaden `case_id`, asignación automática, deprecación, redirect ni cambios a
la API. La Red continúa siendo una proyección NetworkX/PyVis derivada,
reconstruible y sin condición de fuente de verdad.

## Estado actual

Las matrices HPN, sus nodos `fact`, `evidence` y `norm`, cuatro relaciones dirigidas, revisión manual, fuentes y borrado lógico están **existentes**. NetworkX, la API JSON, PyVis offline y el frontend de Red están **existentes**. Ambos dominios son hoy globales y por ello son **legado operativo** respecto del futuro workspace de casos.

La fuente se resuelve mediante documento, chunk y rango de páginas, con
fingerprint interno y estado público resumido. Los contratos no deben exponer
fingerprints, rutas ni identificadores internos de chunks. Las matrices
`archived` permanecen visibles y de solo lectura; elementos `rejected` impiden
una revisión final y un cambio estructural de una matriz `reviewed` la devuelve
a revisión.

## Lo que se preserva

- estados de matriz `draft`, `in_review`, `reviewed`, `archived`;
- estados de revisión `draft`, `reviewed`, `rejected`;
- relaciones `evidence_supports_fact`, `evidence_contradicts_fact`, `norm_applies_to_fact` y `norm_limits_fact`;
- snapshots y estados `valid`, `stale`, `unavailable` de fuentes;
- invalidación de revisión ante cambios estructurales;
- proyección determinista `nx.DiGraph` y visualización de solo lectura;
- límites, sanitización, alternativa textual y revisión profesional.

## Insuficiencias para casos tras 12E-2

Aunque ya existen `Case` y `CaseDocument`, no hay `case_id` en HPN/Red, versiones
inmutables de matriz, ejecución de origen, gates humanos del pipeline ni
auditoría de cambios como artefactos. La unicidad actual impide duplicar el
mismo tipo de relación activa entre dos nodos, por lo cual `DiGraph` sigue
siendo suficiente; si el dominio futuro admite múltiples afirmaciones
independientes entre el mismo par, deberá evaluarse `MultiDiGraph` mediante una
migración explícita.

## Estrategia de migración

1. Consumir la asociación documental ya implementada cuando exista el pipeline autorizado.
2. Añadir una asociación/versionado HPN de caso sin modificar el significado de matrices existentes.
3. Permitir asignación humana de una matriz histórica a un caso o conservarla como legado sin asignar.
4. Construir la Red desde una versión HPN seleccionada.
5. Validar paridad de API, UI y exportación.
6. Deprecar rutas globales; retirar solo después de una ventana documentada.

## Semántica jurídica limitada

Las aristas expresan una clasificación humana revisable. Una ruta, ciclo, grado, componente o centralidad es una propiedad estructural; no demuestra hechos, suficiencia de evidencia, aplicabilidad normativa, causalidad ni conclusión jurídica.

## Fuentes y trazabilidad

Una fuente HPN de caso debe resolver a `CaseDocument`, `Document` y chunk vigentes. Si pierde elegibilidad o cambia su fingerprint, se conserva para trazabilidad con advertencia y el artefacto pasa a `stale`; no se repara ni aprueba automáticamente.
