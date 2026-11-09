# Proyecto final: detecciones de incendios y anomalías térmicas con NASA FIRMS

Proyecto del curso **Bases de Datos No Relacionales (Otoño 2026)**. El objetivo es construir y documentar una arquitectura distribuida que convierta detecciones satelitales publicadas por [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/) en datos operativos y analíticos. La fuente seleccionada es real; la arquitectura, los procesos y los resultados analíticos todavía están por implementarse.

## Fuente de datos y alcance preliminar

El *Fire Information for Resource Management System* (FIRMS) de NASA distribuye detecciones de fuegos activos y otras anomalías térmicas derivadas de sensores satelitales. Cada fila identifica un píxel donde se detectó una anomalía, con coordenadas, momento de adquisición y mediciones asociadas. **Una detección no equivale necesariamente a un incendio distinto, a su ubicación exacta ni a su superficie quemada**: el punto representa el centro del píxel observado y pueden existir otras fuentes de calor o falsos positivos.

La propuesta inicial es consultar datos **VIIRS de NOAA-20 y NOAA-21 a escala mundial**, sujetos a validación con el equipo y con pruebas de disponibilidad y caudal. MODIS puede incorporarse si resulta necesario y se documentan las diferencias entre sensores y productos. NASA FIRMS publica resultados de la API en **lotes CSV**, no mediante un flujo de eventos individual de tipo push. El proyecto propone consultar periódicamente la API, identificar las detecciones nuevas, deduplicarlas y emitirlas como eventos hacia el sistema de ingesta. La frecuencia de consulta, la latencia, los criterios de identidad y el manejo de correcciones están pendientes de diseño y prueba.

### Enlaces oficiales

- [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/)
- [API Area de FIRMS: fuentes, formato de solicitud y área geográfica](https://firms.modaps.eosdis.nasa.gov/api/area/)
- [Atributos de datos de incendios activos MODIS y VIIRS](https://www.earthdata.nasa.gov/data/tools/firms/active-fire-data-attributes-modis-viirs)
- [Preguntas frecuentes de FIRMS: significado de la detección, latencia y limitaciones](https://www.earthdata.nasa.gov/data/tools/firms/faq)

La API Area utiliza una clave `MAP_KEY` y permite solicitar CSV con una fuente, un área (`world` o límites geográficos), un rango de 1 a 5 días y, opcionalmente, una fecha de inicio. Para el alcance preliminar, las fuentes son `VIIRS_NOAA20_NRT` y `VIIRS_NOAA21_NRT`. El patrón documentado por NASA es `https://firms.modaps.eosdis.nasa.gov/api/area/csv/[MAP_KEY]/[SOURCE]/[AREA_COORDINATES]/[DAY_RANGE]`, con un segmento opcional `[DATE]`. **No publicar claves reales ni URL que las incluyan** en el repositorio, incidencias, capturas o registros. La clave se suministrará mediante una variable de entorno al ejecutar el consumidor.

## Origen y autoría

Los sensores VIIRS a bordo de NOAA-20 y NOAA-21 producen las observaciones satelitales; NASA LANCE FIRMS procesa y distribuye las detecciones de incendios activos para su consulta. Los datos NRT se publican después del paso del satélite y su latencia global puede ser de hasta unas horas según el producto y la disponibilidad. La periodicidad de publicación no equivale a una detección nueva por segundo en cada instante.

## Diccionario de datos preliminar: VIIRS NRT

Las definiciones siguientes proceden de la [tabla oficial de atributos de NASA](https://www.earthdata.nasa.gov/data/tools/firms/active-fire-data-attributes-modis-viirs). Los nombres y campos exactos del CSV de la API se contrastarán con una respuesta guardada para cada producto antes de cerrar el esquema de ingesta. En los servicios web NASA también denomina `brightness` a `bright_ti4` y `brightness_2` a `bright_ti5`.

| Campo | Naturaleza | Descripción |
| --- | --- | --- |
| `latitude` | Cuantitativa / geográfica | Latitud del centro del píxel detectado, en grados. |
| `longitude` | Cuantitativa / geográfica | Longitud del centro del píxel detectado, en grados. |
| `bright_ti4` (`brightness` en servicios web) | Cuantitativa | Temperatura de brillo del canal VIIRS I-4, en kelvin. |
| `scan` | Cuantitativa | Dimensión del píxel en la dirección de barrido; varía con la geometría de observación. |
| `track` | Cuantitativa | Dimensión del píxel en la dirección de avance orbital. |
| `acq_date` | Temporal | Fecha de adquisición de la detección. |
| `acq_time` | Temporal | Hora de adquisición en UTC; debe interpretarse junto con `acq_date`. |
| `satellite` | Cualitativa | Plataforma de origen, por ejemplo `N20` o `N21`. |
| `confidence` | Cualitativa | Confianza VIIRS baja, nominal o alta; no es un porcentaje como en MODIS. |
| `version` | Cualitativa | Colección y modalidad de procesamiento del producto. |
| `bright_ti5` (`brightness_2` en servicios web) | Cuantitativa | Temperatura de brillo del canal VIIRS I-5, en kelvin. |
| `frp` | Cuantitativa | Potencia radiativa estimada del píxel, en megavatios (MW). |
| `daynight` | Cualitativa | Indicador de observación diurna (`D`) o nocturna (`N`). |

Estos 13 atributos están descritos en la tabla de NASA para VIIRS NRT. Una prueba previa comunicada por el equipo reportó **14 columnas en una respuesta de FIRMS**; la columna adicional y las diferencias de nombre quedan pendientes de comprobar directamente en la respuesta de la API. La fuente no ofrece un campo de texto libre como parte de este diccionario preliminar. Las series temporales se construirán combinando `acq_date` y `acq_time` en UTC, distinguiendo la hora de observación de la de publicación e ingesta cuando esas marcas se registren en el pipeline.

## Caudal y viabilidad del requisito de stream

La rúbrica exige un promedio mínimo de **1 evento por segundo** y permite combinar fuentes. En una revisión previa comunicada por el equipo, para el **8 de noviembre de 2026** a escala mundial se reportaron **119 498 detecciones VIIRS NOAA-20 y NOAA-21**, equivalentes a aproximadamente **1,38 detecciones por segundo** en ese día; al añadir MODIS se reportaron **131 462 detecciones**, aproximadamente **1,52 por segundo**. Son antecedentes de una sola fecha, **no mediciones reproducidas en este repositorio ni garantía de caudal sostenido, entrega uniforme o eventos nuevos en cada segundo**. Se medirá el volumen en varios días, separado por producto, y se registrará tanto el caudal de detecciones únicas como el de eventos realmente ingresados sin pérdida. También se consultará al profesor si acepta el esquema de consulta periódica y emisión de eventos como stream del proyecto.

## Consideraciones éticas y limitaciones

Las detecciones pueden omitirse por nubosidad, humo, cobertura vegetal, tamaño o duración del fuego, e incluir otras anomalías o artefactos. Las diferencias de resolución, latencia, cobertura y confianza entre productos impiden comparar recuentos o potencia radiativa como si representaran automáticamente número de incendios, daños o riesgo humano. Las consultas y visualizaciones deben conservar el origen del satélite, el producto, las marcas temporales y la incertidumbre; no se publicarán coordenadas como confirmación de un incendio puntual sin verificación independiente. El uso de los datos respetará la atribución recomendada por [NASA FIRMS](https://www.earthdata.nasa.gov/data/tools/firms/faq).

## Plan de implementación y documentación

1. **Validación de la fuente:** fijar productos y región, capturar encabezados reales, medir varios días de datos y acordar con el profesor el mecanismo de conversión de lotes a eventos.
2. **Infraestructura:** documentar y desplegar una base NoSQL operativa con replicación y sharding, una capa analítica apropiada, control de accesos, diagramas y una justificación explícita en términos de CAP. Las tecnologías concretas aún no están elegidas.
3. **Ingesta:** implementar consulta periódica, deduplicación, manejo de errores, inserción y consultas puntuales; medir caudal, pérdida y recuperación ante fallos.
4. **Procesamiento:** limpiar y tipar datos, enriquecerlos con fuentes estáticas cuando aporte valor, conservar trazabilidad y preparar agregaciones analíticas.
5. **Resultados:** ejecutar al menos cinco consultas analíticas complejas, explicar hallazgos e impacto, y mostrar la evolución desde el CSV crudo hasta la información transformada.

El código, las instrucciones de ejecución, las pruebas, las decisiones de diseño, los diagramas y los resultados se incorporarán a este repositorio conforme se implementen. Hasta entonces, este README documenta **la fuente elegida y el estado preliminar**, no una arquitectura ya desplegada.
