# Seguridad y privacidad

## Procesamiento local

Los documentos, embeddings, índices y generación se procesan localmente. SQLite conserva la fuente de verdad; FTS5 y ChromaDB son índices derivados. No se usan servicios externos para inferencia jurídica.

## Fuentes y gobernanza

El producto distingue corpus administrado, biblioteca privada, documentos temporales y futuras fuentes web verificadas. Los documentos privados no pasan automáticamente al corpus general. Las fuentes web futuras requerirán procedencia, vigencia, permisos, conservación y revisión.

## Documentos y rutas

La carga acepta PDF con límites de tamaño, validación de MIME, extensión y firma. Los nombres se normalizan y las rutas se validan para impedir traversal y escapes del almacenamiento autorizado. Los PDF pueden contener contenido malicioso o instrucciones no confiables; nunca se tratan como instrucciones del sistema.

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
