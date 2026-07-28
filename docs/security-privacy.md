# Seguridad y privacidad

## Procesamiento local

Los documentos, embeddings, índices y generación se procesan localmente. SQLite conserva la fuente de verdad; FTS5 y ChromaDB son índices derivados. No se usan servicios externos para inferencia jurídica.

## Fuentes y gobernanza

El producto distingue corpus administrado, biblioteca privada, documentos temporales y futuras fuentes web verificadas. Los documentos privados no pasan automáticamente al corpus general. Las fuentes web futuras requerirán procedencia, vigencia, permisos, conservación y revisión.

La elegibilidad documental es calculada y no se persiste como autorización. La
expiración de un documento temporal lo excluye, pero no elimina automáticamente
su registro, páginas, chunks ni archivo. La API comunica únicamente indicadores
y códigos técnicos tipados, sin rutas, contenido documental ni errores
internos. El borrado lógico, el archivo técnico y el retiro editorial son
condiciones distintas, aunque cualquiera excluye el documento de RAG.

FTS5 y ChromaDB solo proponen candidatos. SQLite vuelve a decidir antes del
resultado, del contexto y de cada cita, incluso cuando el cliente suministra
un `document_id` o una capa. Los documentos vencidos, retirados, rechazados,
archivados, no vigentes, no indexados o candidatos globales se excluyen de
inmediato aunque persistan entradas antiguas en un índice derivado. Los cambios
de gobernanza invalidan de forma detectable el índice semántico; nunca disparan
una reconstrucción automática ni eliminan PDF, páginas o chunks.

## Documentos y rutas

La carga acepta PDF con límites de tamaño, validación de MIME, extensión y firma. Los nombres se normalizan y las rutas se validan para impedir traversal y escapes del almacenamiento autorizado. Los PDF pueden contener contenido malicioso o instrucciones no confiables; nunca se tratan como instrucciones del sistema.

La interfaz envía el PDF únicamente mediante `FormData` al backend local y no
conserva el archivo, su contenido, hashes ni rutas en el navegador. Solo expone
la carga explícita para biblioteca privada o consulta temporal con expiración
futura; el backend conserva la validación autoritativa y la interfaz no inicia
extracción, indexación ni elegibilidad documental.

El staging del corpus administrado se ubica bajo `storage/staging`, permanece
ignorado y no es una carpeta observada. Solo la CLI explícita puede validar o
importar; copiar archivos no altera SQLite. Se rechazan rutas absolutas,
traversal y symlinks, y las salidas no muestran rutas ni hashes completos. La
importación nunca aprueba, procesa o indexa automáticamente una fuente.

## RAG y modelo

El texto recuperado se delimita y neutraliza antes de construir el prompt. Los documentos no reentrenan Qwen y el conocimiento previo del modelo no es una fuente jurídica verificable. Las preguntas, respuestas, prompts y contenido documental no deben registrarse ni persistirse accidentalmente.

## Matrices HPN y revisión profesional

Las relaciones HPN y la Red jurídica son herramientas de organización y revisión. Las propuestas futuras de IA serán borradores. No se debe afirmar automáticamente que un hecho está probado, que una prueba es suficiente ni que una norma es aplicable.

## Información no expuesta en frontend

El contrato público ordinario de documentos no devuelve nombres almacenados,
rutas relativas o absolutas, hashes ni mensajes técnicos internos. Esos datos
permanecen disponibles únicamente para los servicios internos que coordinan
almacenamiento, duplicados y extracción.

Tampoco se deben mostrar secretos, prompts, vectores, identificadores
restringidos, contenido no autorizado o HTML no confiable. Las respuestas y
errores deben usar contratos sanitizados.

La política técnica de logs está en [logging.md](logging.md).
