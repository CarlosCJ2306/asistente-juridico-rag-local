# Producto y alcance

## Problema y usuarios

El Asistente Jurídico Local ayuda a profesionales a organizar evidencia documental y consultar información recuperada con trazabilidad. Está dirigido a usuarios que trabajan con documentos privados y necesitan conservar control local, revisión humana y referencias verificables.

## Experiencia principal

El flujo objetivo es: incorporar un PDF autorizado, administrarlo en una biblioteca local, extraer páginas y fragmentos, recuperar evidencia, consultar el Chat RAG con citas y estructurar posteriormente hechos, pruebas y normas para revisión mediante Matrices HPN y Red jurídica.

Las conversaciones de invitado permiten repreguntas y conservan el historial
local durante siete días desde la última actividad. Cada turno vuelve a obtener
evidencia documental; una respuesta anterior no constituye fuente jurídica.
No existen cuentas, login, transferencia ni sincronización entre dispositivos:
esas capacidades futuras requerirán autenticación real y consentimiento.

El Chat ocupa todo el espacio útil restante del App Shell y es el área principal de trabajo: las fuentes pertenecen a cada
respuesta y se inspeccionan bajo demanda. La información de sesión y la
advertencia de revisión profesional permanecen visibles de forma discreta, sin
competir con el hilo ni el composer.

## Alcance actual

El backend ya registra y carga PDF de forma segura, extrae texto con PyMuPDF, persiste páginas y chunks, recupera evidencia con FTS5 y ChromaDB, construye contexto RAG, genera con Qwen local y devuelve citas estructuradas. También existen Matrices HPN manuales, una API de grafo y exportación PyVis.

La biblioteca incorpora procesamiento automático: una carga manual o un PDF
estable depositado en una bandeja controlada entra en una cola persistente,
se extrae y se incorpora al índice semántico mediante un lote atómico. Los
temporales requieren expiración futura y los sidecars inválidos terminan en
cuarentena. Esto no aprueba automáticamente el corpus administrado.

El operador puede consultar un catálogo cerrado de modelos locales instalados y
seleccionar de forma persistente el modelo de embeddings o el LLM activo. La
selección no descarga ni carga modelos y no reconstruye índices.

El Centro de modelos conserva selección y controles avanzados. En el flujo
documental normal, embeddings puede cargarse bajo demanda y liberarse tras
inactividad. Cambiar embeddings puede
exigir reconstruir explícitamente el índice antes de buscar; seleccionar o
cargar el LLM no modifica ese índice y no inicia el Chat futuro.

El frontend actual ofrece Inicio, Asistente jurídico conversacional, Casos como
estado vacío preparatorio, Biblioteca documental, Búsqueda documental, Modelos
locales, Matrices HPN y Red jurídica.
La biblioteca permite conocer los metadatos públicos, la procedencia
y la elegibilidad para consultas, además de registrar de forma explícita un PDF
en biblioteca privada o como consulta temporal con expiración futura. No muestra
el contenido ni inicia cambios de gobernanza desde la interfaz. La búsqueda
documental utiliza la recuperación híbrida ya gobernada y no inicia
procesamiento ni indexación. Chat, historial invitado y fuentes visibles ya
existen. El backend ya dispone del núcleo persistente `Case`, `/api/cases` y
pertenencia explícita a documentos privados o temporales existentes. Todavía
no hay workspace conectado; `/cases` solo presenta una estructura visual
preparatoria.

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
El flujo es pregunta → recuperación gobernada → evidencia revalidada → respuesta
local → citas verificables. Tras revalidar en SQLite, selecciona contexto con
presupuesto de tokens y solo entonces carga y llama a Qwen local. Si no queda
evidencia elegible, devuelve contexto insuficiente sin inicializar Qwen ni
completar desde el conocimiento previo del modelo.

La búsqueda recupera candidatos trazables; el Chat añade selección de contexto,
generación limitada y validación de citas. Sus citas estructuradas identifican
la capa y evidencia usada. El Asistente jurídico presenta este flujo principal
como pregunta → evidencia → respuesta → fuentes, mientras la búsqueda
documental conserva su papel técnico avanzado. El endpoint individual mantiene
cada pregunta independiente. El dominio conversacional permite además hilos
invitados temporales: cada turno usa una ventana acotada para interpretar
referencias y recupera evidencia nueva. Las respuestas persistidas incluyen
claims, citas directas limitadas y cobertura `full`, `partial` o
`insufficient`; el flujo estricto vigente produce cobertura completa o
insuficiente y mantiene `partial` preparado sin presentar contenido no
sustentado. Toda respuesta requiere revisión profesional.

Las conversaciones invitadas se retienen siete días desde la última actividad.
Las cuentas persistentes y la transferencia con consentimiento están preparadas
en el dominio, pero solo se habilitarán cuando exista autenticación real.

## Matrices HPN y Red jurídica

Las Matrices HPN permiten registrar manualmente hechos, evidencias, normas y relaciones revisables. La Red jurídica es una proyección estructural local y de solo lectura de esas matrices. No representa conclusiones jurídicas automáticas.

La edición manual HPN sigue siendo necesaria: futuras propuestas de IA serán borradores, no hechos probados ni decisiones. La revisión y aprobación humana determinan su uso.

## Arquitectura de producto objetivo desde 12D

La evolución separa tres áreas. 12E-1 inició el segundo límite en backend y
12E-2 incorporó su pertenencia documental explícita:

- **Asistente jurídico general:** Chat y conversaciones locales no ligadas a un expediente.
- **Workspace de inteligencia de casos:** ya cuenta con el agregado persistente
  `Case` y asociaciones `CaseDocument`; carga directa, HPN, Red, métricas,
  escenarios, asistencia y frontend conectado continúan planificados.
- **Plataforma local compartida:** documentos, gobernanza, procesamiento,
  recuperación, modelos, persistencia, observabilidad y contratos comunes.

HPN y Red son hoy globales y siguen operativas como legado. No se considerarán
recursos de caso hasta existir una asociación explícita y validada. La
[definición del workspace](case-workspace.md) y el
[dominio de casos](case-domain.md) distinguen capacidades existentes de las
planificadas.
