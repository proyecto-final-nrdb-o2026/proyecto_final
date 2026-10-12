# Stream `recentchange` de Wikimedia

## Resumen del stream

`recentchange` transmite eventos del feed de cambios recientes de MediaWiki: ediciones, creación de páginas, registros, cambios de categorías y otros cambios externos. Cada evento describe el cambio mediante metadatos como su tipo, página, wiki, marca temporal, usuario y comentario; en eventos de edición puede incluir además longitudes y revisiones anterior y nueva. No contiene por defecto el texto completo del artículo. El endpoint entrega eventos continuamente en tiempo real mediante EventStreams sobre HTTP/SSE. [EventStreams](https://wikitech.wikimedia.org/wiki/Event_Platform/EventStreams_HTTP_Service) · [Manual del feed Recent Changes](https://www.mediawiki.org/wiki/Manual:RCFeed/en)

El stream reúne cambios de distintos proyectos y wikis Wikimedia. El atributo `wiki` identifica la base de datos del wiki (por ejemplo `enwiki`, `commonswiki` o `wikidatawiki`); `server_name` identifica el nombre de servidor y permite distinguir el dominio asociado. [Documentación de EventStreams](https://wikitech.wikimedia.org/wiki/Event_Platform/EventStreams_HTTP_Service)

- Endpoint: [https://stream.wikimedia.org/v2/stream/recentchange](https://stream.wikimedia.org/v2/stream/recentchange)
- Servicio: [EventStreams HTTP Service](https://wikitech.wikimedia.org/wiki/Event_Platform/EventStreams_HTTP_Service)
- Especificación del feed: [Manual:RCFeed](https://www.mediawiki.org/wiki/Manual:RCFeed/en)
- Esquema vigente: [current.yaml en GitHub](https://github.com/wikimedia/mediawiki-event-schemas/blob/master/jsonschema/mediawiki/recentchange/current.yaml)

## Origen y autoría

La Wikimedia Foundation (WMF) opera la infraestructura pública EventStreams, que expone flujos de eventos mediante HTTP y Server-Sent Events y se respalda internamente en Kafka. Los eventos `recentchange` se originan en MediaWiki cuando personas o sistemas automatizados realizan acciones que producen entradas de cambios recientes en los wikis. Por ello, la WMF mantiene y publica el servicio de distribución, mientras que quienes editan —personas o bots— originan las acciones registradas; ambos papeles no deben confundirse. [EventStreams: descripción y arquitectura](https://wikitech.wikimedia.org/wiki/Event_Platform/EventStreams_HTTP_Service) · [Manual:RCFeed](https://www.mediawiki.org/wiki/Manual:RCFeed/en)

## Diccionario de datos

La tabla sigue el [esquema JSON vigente](https://github.com/wikimedia/mediawiki-event-schemas/blob/master/jsonschema/mediawiki/recentchange/current.yaml) y el esquema común al que este remite. En JSON Schema, si un atributo no aparece en una lista `required`, no queda garantizado por el esquema. La definición de `recentchange` no declara como obligatorios sus campos específicos; el esquema común exige el objeto `meta` y el sobre del evento `$schema` y `dt`. Además, se permiten propiedades adicionales para mantener compatibilidad. Por tanto, la presencia real depende del tipo de evento y de la wiki. “No admite nulo” describe el tipo declarado, no una garantía de presencia.

| Atributo / ruta | Tipo según esquema | Presencia / nulabilidad | Significado funcional | Ejemplo documentado |
|---|---|---|---|---|
| `$schema` | cadena | Obligatorio; no nulo | URI/identificador del esquema del evento. | `/mediawiki/recentchange/1.0.0` |
| `dt` | cadena, fecha-hora (ISO 8601) | Obligatorio; no nulo | Fecha y hora del evento en el sobre común. | `2022-07-12T17:54:15Z` |
| `meta` | objeto | Obligatorio; no nulo | Metadatos comunes del evento. | — |
| `meta.domain` | cadena | Opcional en esta tabla (miembro de `meta`); no se admite nulo en su tipo documentado | Dominio asociado al evento. EventStreams lo usa en ejemplos para identificar eventos canary. | `www.wikidata.org` |
| `meta.dt` | cadena | Opcional; el ejemplo de evento la expresa como fecha-hora ISO 8601 | Fecha y hora del evento en metadatos. La definición común la documenta como timestamp ISO 8601. | `2022-07-12T17:54:15Z` |
| `meta.id` | cadena | Opcional; no nulo en el ejemplo documentado | Identificador único del evento en metadatos. | `2cdec62f-a2b3-49b8-9a52-85a42236fb99` |
| `meta.offset` | entero | Opcional; no nulo en el ejemplo documentado | Desplazamiento/posición asociado al evento. | `4000957901` |
| `meta.partition` | entero | Opcional; no nulo en el ejemplo documentado | Partición asociada al evento. | `0` |
| `meta.request_id` | cadena | Opcional; no nulo en el ejemplo documentado | Identificador de solicitud asociado al evento. | `f7896e77-fd2b-4a95-a9e4-44c1e3ad818b` |
| `meta.stream` | cadena | Opcional; no nulo en el ejemplo documentado | Nombre del stream. | `mediawiki.recentchange` |
| `meta.topic` | cadena | Opcional; no nulo en el ejemplo documentado | Tema Kafka de origen. | `eqiad.mediawiki.recentchange` |
| `meta.uri` | cadena | Opcional; no nulo en el ejemplo documentado | URI asociada al evento/página. | `https://www.wikidata.org/wiki/Q2190037` |
| `id` | entero o nulo | Opcional; admite nulo | ID de la entrada de cambio reciente (`rcid`). | `1728475074` |
| `type` | cadena | Opcional; no nulo si está presente | Tipo de evento; valores principales: `edit`, `new`, `log`, `categorize` o `external`. | `edit` |
| `title` | cadena | Opcional; no nulo si está presente | Nombre completo de la página afectada, con prefijo de espacio de nombres. | `Q2190037` |
| `namespace` | entero | Opcional; no nulo si está presente | ID del espacio de nombres afectado; el esquema indica `-1` para eventos de log. | `0` |
| `comment` | cadena | Opcional; no nulo si está presente | Comentario de la entrada de cambio reciente (`rc_comment`). | `sorting image request` |
| `parsedcomment` | cadena | Opcional; no admite nulo según el tipo declarado | Comentario parseado como HTML simple. | `<span dir="auto">…</span>` |
| `timestamp` | entero | Opcional; no nulo si está presente | Timestamp Unix derivado de `rc_timestamp`. | `1657648455` |
| `user` | cadena | Opcional; no nulo si está presente | Texto del usuario (`rc_user_text`). | `KrBot` |
| `bot` | booleano | Opcional; no nulo si está presente | Indicador de que la entrada fue marcada como bot (`rc_bot`). | `true` |
| `server_url` | cadena | Opcional; no nulo si está presente | Servidor canónico (`$wgCanonicalServer`). | `https://www.wikidata.org` |
| `server_name` | cadena | Opcional; no nulo si está presente | Nombre del servidor (`$wgServerName`). | `www.wikidata.org` |
| `server_script_path` | cadena | Opcional; no nulo si está presente | Ruta del script de MediaWiki (`$wgScriptPath`). | `/w` |
| `wiki` | cadena | Opcional; no nulo si está presente | Identificador del wiki (`wfWikiID`, derivado de configuración de base de datos). | `wikidatawiki` |
| `minor` | booleano | Opcional; campo asociado a eventos `edit` y `new`; no admite nulo | Indicador de cambio menor (`rc_minor`). | `false` |
| `patrolled` | booleano | Opcional; asociado a edición/nueva página y solo presente si la wiki admite patrullaje para ese evento; no admite nulo | Indicador de patrullaje (`rc_patrolled`). | `true` |
| `length` | objeto | Opcional; asociado a eventos `edit` y `new` | Longitud anterior y nueva del cambio. | — |
| `length.old` | entero o nulo | Opcional; admite nulo | Longitud anterior (`rc_old_len`); puede ser nula cuando no hay longitud anterior, por ejemplo al crear una página. | `186` |
| `length.new` | entero o nulo | Opcional; admite nulo | Longitud nueva (`rc_new_len`). | `219` |
| `revision` | objeto | Opcional; asociado a eventos `edit` y `new` | Identificadores de revisión anterior y nueva. | — |
| `revision.new` | entero o nulo | Opcional; admite nulo | Campo descrito en el esquema como `rc_last_oldid`. | `649690049` |
| `revision.old` | entero o nulo | Opcional; admite nulo | Campo descrito en el esquema como `rc_this_oldid`. | `649645633` |
| `log_id` | entero o nulo | Opcional; campo asociado a eventos `log`; admite nulo | ID del registro (`rc_log_id`). | — |
| `log_type` | cadena o nulo | Opcional; campo asociado a eventos `log`; admite nulo | Tipo de registro (`rc_log_type`). | — |
| `log_action` | cadena | Opcional; campo asociado a eventos `log`; no admite nulo | Acción del registro (`rc_log_action`). | — |
| `log_params` | arreglo, objeto o cadena | Opcional; solo se incluye si el evento tiene `rc_params`; el tipo no declara `null` | Parámetros del registro; para objetos se permiten propiedades adicionales. | — |
| `log_action_comment` | cadena o nulo | Opcional; asociado a eventos de log; admite nulo | Comentario de la acción de log. El esquema no ofrece una definición funcional más específica. | — |

**Nota sobre `revision`:** el esquema vigente etiqueta `revision.new` como `rc_last_oldid` y `revision.old` como `rc_this_oldid`, mientras que el manual del feed describe los nombres en sentido opuesto (`revision.new` como revisión nueva/`rc_this_oldid` y `revision.old` como revisión anterior/`rc_last_oldid`). Se conserva arriba la asociación literal del esquema solicitado; para interpretar estos dos subcampos, esta discrepancia documental debe resolverse consultando la versión de implementación o validando eventos reales. [Esquema GitHub](https://github.com/wikimedia/mediawiki-event-schemas/blob/master/jsonschema/mediawiki/recentchange/current.yaml) · [Manual:RCFeed](https://www.mediawiki.org/wiki/Manual:RCFeed/en)

Los ejemplos se toman del manual y de un ejemplo de evento citado por la documentación de Pywikibot; los guiones indican que el esquema o la documentación consultada no proporcionan un ejemplo concreto para ese campo. [Ejemplos del manual](https://www.mediawiki.org/wiki/Manual:RCFeed/en) · [Evento de ejemplo en Pywikibot](https://github.com/wikimedia/pywikibot/blob/master/pywikibot/comms/eventstreams.py)

## Clasificación de variables

- **Cuantitativos:** `id`, `namespace`, `timestamp`, `length.old`, `length.new`, `revision.new`, `revision.old` y `log_id` son numéricos según el esquema. Representan identificadores, categorías numéricas o medidas; que un ID sea entero no lo convierte por sí solo en una medida de magnitud. Los subcampos de `meta` `offset` y `partition` también se representan como enteros en el ejemplo de evento documentado.
- **Cualitativos:** `type`, `title`, `user`, `wiki`, `server_url`, `server_name`, `server_script_path`, `log_type`, `log_action`, `log_params` y los identificadores textuales de `meta` son cadenas u otros valores nominales/categóricos. `bot`, `minor` y `patrolled` son indicadores booleanos, no medidas continuas. `namespace` también puede usarse como categoría pese a su codificación numérica.
- **Texto no estructurado:** `comment` y `log_action_comment` contienen comentarios; `parsedcomment` contiene su representación HTML parseada. Aunque `log_params` puede ser una cadena, un arreglo u objeto, el esquema no define una semántica común de texto libre para todas sus formas.
- **Series temporales:** `timestamp` es un entero Unix y `dt`/`meta.dt` son fechas-horas ISO 8601. La clasificación temporal se refiere al significado cronológico, aunque sus tipos de almacenamiento difieran.

Un mismo atributo puede tener más de una lectura analítica: `namespace` es entero pero representa una categoría; los IDs son numéricos pero nominales; `timestamp` es numérico en el esquema y temporal por significado.

## Consideraciones éticas

Los eventos pueden exponer nombres de usuario, títulos de páginas, dominios/URIs y comentarios públicos. Estos elementos pueden permitir reconocer o vincular actividad, incluso sin que el esquema incluya datos de contacto o atributos personales adicionales. Los comentarios pueden contener referencias identificables o contexto sensible escrito por quienes editan, por lo que su disponibilidad pública no elimina el deber de usarlos con cuidado.

Los títulos y comentarios aparecen en distintos idiomas y convenciones editoriales. Una comparación automática puede confundir diferencias lingüísticas o de formato con diferencias de calidad. Asimismo, `bot` es un indicador operativo, no una evaluación de intención; `minor`, el tamaño del cambio o una reversión aislada no prueban vandalismo ni calidad. El stream aporta metadatos del cambio y no basta por sí solo para inferir motivos o conclusiones sobre personas.

Para reducir riesgos, en reportes agregados omite `user`, IDs de evento/revisión y otros identificadores cuando no sean necesarios; evita republicar comentarios textuales o títulos identificables innecesariamente; limita el acceso y la retención a lo necesario para el análisis; interpreta comparaciones por idioma y wiki con su contexto; y no etiquetes una edición como maliciosa basándote únicamente en el tamaño, el indicador de bot o la presencia de una reversión.
