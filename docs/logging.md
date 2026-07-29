# Logging y protección de información

## Implementación

El módulo canónico es `backend/app/core/Log.py` y todos los imports deben usar
exactamente `from app.core.Log import ...`. El logger interno se denomina
`asistente_juridico_backend`, no propaga registros al logger raíz y utiliza una
marca interna para no duplicar handlers.

La salida incluye fecha, nivel, logger, archivo, línea y mensaje. Puede enviarse
a consola y a un `RotatingFileHandler` UTF-8. Por defecto, el archivo absoluto
resuelve a:

```text
storage/logs/asistente_juridico_backend.log
```

El tamaño, número de copias, nivel y destinos se controlan desde `.env`.

## API pública

La API incluye `get_logger`, funciones para los niveles estándar, `log_success`
(SUCCESS=25), `log_documentation` (DOC=15), `log_exception`, `log_step`,
`get_log_file_path` y el context manager `LogStep`. Las excepciones conservan
su traza completa y `LogStep` nunca las suprime.

## Política de contenido

## Compatibilidad legacy

Las políticas puras de transición 12D-3 no requieren logging. Si un adaptador
legacy falla, solo puede registrar operación, adaptador, etapa, código seguro,
tipo de excepción y `request_id`; nunca DTOs, títulos, statements, fuentes,
objetos NetworkX o HTML.

Está prohibido registrar:

- texto completo de expedientes o contenido completo de chunks;
- prompts o respuestas completas de modelos;
- cuerpos completos de solicitudes y parámetros sensibles;
- contraseñas, tokens, autorizaciones, cookies, secretos o claves de API;
- datos personales sensibles y contenido binario.

Se permiten únicamente metadatos técnicos necesarios, por ejemplo:
`request_id`, `document_id`, `chunk_id`, `conversation_id`, `page_count`,
`chunk_count`, `file_size`, `duration_ms`, `status_code` y `exception_type`.
Para `Case` se permiten operación, estado, versión, duración y código estable;
no se registran título, descripción, cookie ni hash de propietario. La
auditoría estructurada de dominio no sustituye esta política de logs.
Para `CaseDocument` se permiten operación, propósito, versión, cantidades y
código estable. No se registran nombres documentales, snapshots, rutas, hashes,
texto, páginas, chunks ni metadatos internos de almacenamiento.

`security_logging.py` enmascara claves sensibles dentro del contexto
estructurado y omite binarios. Esta protección es una última barrera, no una
autorización para pasar contenido jurídico al logger: quien invoque el logger
debe seleccionar previamente solo metadatos seguros.

El middleware registra método y ruta, pero nunca cuerpos ni cadenas de consulta.
