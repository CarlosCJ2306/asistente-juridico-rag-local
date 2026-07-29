# Dominio de casos

## Estado

**Núcleo y pertenencia documental implementados en 12E-1/12E-2.** Existen
dominio independiente del ORM, migraciones, repositorios, servicios,
`/api/cases` y subrutas documentales. El frontend `/cases` continúa estático.
No existen todavía rutas frontend dinámicas, pipeline, conversaciones de caso
ni vínculos con HPN/Red.

## Agregado `Case`

`Case` es el límite de consistencia implementado para identidad, propiedad,
retención, estado, versión y auditoría base. No reemplaza `Document`; la
organización de documentos, ejecuciones y artefactos empieza en bloques
posteriores.

Campos conceptuales mínimos:

- identificador interno opaco y un identificador público estable;
- título y descripción limitados;
- estado `draft`, `active`, `in_review`, `closed` o `archived`;
- modo de retención `temporary` o `local_persistent` y propietario
  `guest_session` o `local_installation`;
- propietario local efectivo, retención, expiración y borrado lógico;
- versión del agregado y fechas técnicas;
- política de acceso y revisión profesional obligatoria.

`account` queda **preparado/futuro**. No se habilitará hasta contar con autenticación real, autorización y consentimiento. No se usará una cookie invitada como cuenta simulada.

## Contrato público implementado

Los recursos se ubican bajo `/api/cases` y exponen
solo identificadores públicos opacos, nombre visible, estado, modo de retención,
fechas públicas y versiones. Hay acciones explícitas para activar, pasar a
revisión, cerrar, archivar y restaurar; `PATCH` no modifica el estado.

Los errores usan códigos estables para no encontrado, archivado,
conflicto de versión, retención inválida, documento no elegible, revisión
requerida, ejecución ocupada y artefacto obsoleto. No devolverán paths, SQL,
tracebacks, hashes documentales o payloads internos.

## Pertenencia documental implementada

`CaseDocument` asocia un caso con un `Document` existente mediante propósito
`primary_record`, `annex`, `evidence` u `other`, orden, versiones y snapshot
mínima. Solo admite las capas `private_library` y `temporary`. No copia PDF,
páginas, chunks, texto, embeddings ni vectores.

Reglas:

- la gobernanza documental global sigue siendo autoritativa;
- pertenecer a un caso no vuelve elegible un documento;
- retirar una asociación establece `removed_at`, no elimina el documento de la biblioteca y permite una nueva asociación explícita sin sobrescribir el historial;
- el borrado lógico o la pérdida de elegibilidad produce una advertencia y vuelve obsoletos los artefactos dependientes;
- una capa temporal conserva su expiración original, salvo una transición explícita permitida por la política documental;
- toda recuperación de caso filtra primero por membresía y vuelve a validar en SQLite.

La lectura calcula `available`, `pending_processing`, `stale`, `expired` o
`unavailable` contra el documento vigente. Una snapshot distinta genera una
advertencia y nunca se actualiza automáticamente. La pertenencia no cambia
capa, revisión, vigencia, extracción, indexación ni elegibilidad RAG.

## Artefactos y versiones

Un artefacto es una salida revisable: entidades, hechos, evidencia, normas, matriz HPN, auditoría HPN, red, métricas, escenarios o dashboard. Cada versión debe registrar:

- `case_id`, tipo, `schema_version` y número de versión;
- estado `draft`, `in_review`, `accepted`, `rejected`, `superseded` o `archived` según el contrato específico;
- fingerprint no reversible de entradas y versión del productor;
- referencias a artefactos predecesores;
- autor/origen local seguro y timestamps;
- decisión humana y motivo estructurado cuando corresponda.

Los artefactos aceptados no se sobrescriben. Una nueva ejecución crea otra versión y conserva la trazabilidad.

## Conversaciones de caso

Serán distintas de las conversaciones generales existentes. Una conversación de caso deberá tener `case_id`, usar únicamente evidencia elegible asociada al caso y respetar la retención del expediente. La migración de conversaciones previas será opt-in; nunca se inferirá un caso a partir del texto.

## Auditoría

`case_audit_events` guarda eventos estructurados: actor local, operación,
transición, versión, resultado y fecha. La mutación y su evento se confirman en
la misma transacción. No guarda título, descripción, prompts, textos jurídicos,
embeddings, rutas, SQL ni razonamiento interno. Los logs operativos no
sustituyen esta auditoría de dominio.

## Retención y eliminación

- `temporary`: expiración obligatoria y rodante de siete días; las lecturas
  autoritativas excluyen o rechazan expirados. La purga física queda pendiente.
- `local_persistent`: retención hasta archivo o eliminación explícita.
- `archived`: visible, inmutable salvo restauración autorizada.
- eliminación: lógica primero; purga física futura, explícita, auditable y separada.

## Invariantes

1. Todo artefacto pertenece a exactamente un caso.
2. Toda fuente de un artefacto resuelve a una asociación documental vigente y a evidencia SQLite vigente.
3. Ningún índice derivado concede elegibilidad ni pertenencia.
4. Ninguna salida automática equivale a hecho probado, norma aplicable o decisión jurídica.
5. Los estados humanos no se promocionan automáticamente por una ejecución.

## Contratos disponibles para la transición

Los ports permiten resolver documentos por lote, consultar/solicitar extracción
oficial, recuperar dentro de un alcance explícito y resumir HPN/Red legacy.
Sus DTO no incluyen rutas, hashes, texto completo, chunk IDs internos,
embeddings, HTML o objetos NetworkX. `ScopedRetrievalPort` todavía no ejecuta
recuperación multi-documento del caso; esa limitación permanece después de
implementar la pertenencia.

## Compatibilidad legacy durante 12E

12D-3 solo permite clasificar y evaluar de manera pura una futura asignación
humana de matrices y redes globales. La evaluación no asigna, aprueba, repara
ni persiste datos. Ya existen `Case` y `CaseDocument`, pero no existe `case_id`
en HPN o Red ni atribución automática de recursos legacy.
