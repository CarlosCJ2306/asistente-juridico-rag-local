# Producto y alcance

## Problema y usuarios

El Asistente Jurídico Local ayuda a profesionales a organizar evidencia documental y consultar información recuperada con trazabilidad. Está dirigido a usuarios que trabajan con documentos privados y necesitan conservar control local, revisión humana y referencias verificables.

## Experiencia principal

El flujo objetivo es: incorporar un PDF autorizado, administrarlo en una biblioteca local, extraer páginas y fragmentos, recuperar evidencia, consultar el Chat RAG con citas y estructurar posteriormente hechos, pruebas y normas para revisión mediante Matrices HPN y Red jurídica.

## Alcance actual

El backend ya registra y carga PDF de forma segura, extrae texto con PyMuPDF, persiste páginas y chunks, recupera evidencia con FTS5 y ChromaDB, construye contexto RAG, genera con Qwen local y devuelve citas estructuradas. También existen Matrices HPN manuales, una API de grafo y exportación PyVis.

El frontend actual ofrece Inicio, Biblioteca documental, Matrices HPN y Red
jurídica. La biblioteca permite conocer los metadatos públicos, la procedencia
y la elegibilidad para consultas, además de registrar de forma explícita un PDF
en biblioteca privada o como consulta temporal con expiración futura. No muestra
el contenido ni inicia procesamiento, indexación o cambios de gobernanza desde
la interfaz. El procesamiento, la selección de corpus, Chat y fuentes visibles
en frontend aún no existen.

## Capas de conocimiento

El flujo técnico visible es registrado → extraído → indexado. La extracción
local genera páginas y fragmentos, pero no hace disponible un documento para
consultas hasta que exista indexación y se cumpla la gobernanza aplicable.

- **Corpus administrado:** documentos aprobados para el uso permitido por su gobernanza.
- **Biblioteca privada:** documentos locales del usuario que no pasan automáticamente al corpus administrado.
- **Documentos temporales:** material con conservación y permisos limitados.
- **Fuentes web futuras:** solo podrán incorporarse con procedencia, vigencia y revisión verificables.
- **Conocimiento previo del modelo:** puede influir en la generación, pero no es una fuente jurídica verificable.

La elegibilidad RAG se calcula en cada lectura: el corpus administrado y las
fuentes web verificadas requieren aprobación y vigencia actual; la biblioteca
privada admite revisión no requerida o aprobada y vigencia desconocida o
actual; los documentos temporales requieren una expiración futura. Todas estas
capas requieren extracción completa e indexación confirmada. Los candidatos
globales no son elegibles mientras permanezcan en esa capa.

Los PDF no reentrenan el modelo; se usan como evidencia recuperada mediante RAG.

## Incorporación al corpus administrado

Copiar un PDF al staging solo lo deja disponible para una operación local:
no crea registros ni inicia procesamiento. `validate` comprueba manifiesto,
archivo, hash y duplicados sin escribir. `import` almacena el documento como
pendiente y no elegible. Una revisión humana separada puede aprobarlo y definir
su vigencia, pero la elegibilidad RAG solo llega después de extracción,
fragmentación e indexación confirmadas por los mecanismos oficiales.

## Chat RAG

El Chat RAG utiliza únicamente evidencia documental que continúe elegible según
su capa, revisión, vigencia, expiración, archivo, extracción e indexación. Los
filtros y un identificador documental explícito no omiten esa comprobación.
Tras revalidar en SQLite, selecciona contexto con presupuesto de tokens y solo
entonces llama a Qwen local. Si no queda evidencia elegible, devuelve contexto
insuficiente sin completar desde el conocimiento previo del modelo. Sus citas
estructuradas identifican la capa y evidencia usada. Una respuesta requiere
revisión profesional y no certifica veracidad, aplicabilidad o suficiencia
jurídica.

## Matrices HPN y Red jurídica

Las Matrices HPN permiten registrar manualmente hechos, evidencias, normas y relaciones revisables. La Red jurídica es una proyección estructural local y de solo lectura de esas matrices. No representa conclusiones jurídicas automáticas.

La edición manual HPN sigue siendo necesaria: futuras propuestas de IA serán borradores, no hechos probados ni decisiones. La revisión y aprobación humana determinan su uso.
