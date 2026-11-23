# Proyecto final: detecciones de incendios y anomalías térmicas con NASA FIRMS

Proyecto del curso **Bases de Datos No Relacionales (Otoño 2026)**. El objetivo es construir y documentar una arquitectura distribuida que convierta detecciones satelitales publicadas por [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/) en datos operativos y analíticos. La fuente seleccionada es real; la arquitectura, los procesos y los resultados analíticos todavía están por implementarse.

## Fuente de datos y alcance preliminar

El *Fire Information for Resource Management System* (FIRMS) de NASA distribuye detecciones de fuegos activos y otras anomalías térmicas derivadas de sensores satelitales. Cada fila identifica un píxel donde se detectó una anomalía, con coordenadas, momento de adquisición y mediciones asociadas. **Una detección no equivale necesariamente a un incendio distinto, a su ubicación exacta ni a su superficie quemada**: el punto representa el centro del píxel observado y pueden existir otras fuentes de calor o falsos positivos.

La propuesta inicial es consultar datos **VIIRS de NOAA-20 y NOAA-21 a escala mundial**, sujetos a validación con el equipo y con pruebas de disponibilidad y caudal. El alcance inicial queda limitado a NOAA-20 y NOAA-21; S-NPP y MODIS no se incluyen en esta etapa. NASA FIRMS publica resultados de la API en **lotes CSV**, no mediante un flujo de eventos individual de tipo push. El proyecto propone consultar periódicamente la API, identificar las detecciones nuevas, deduplicarlas y emitirlas como eventos hacia el sistema de ingesta. La frecuencia de consulta, la latencia, los criterios de identidad y el manejo de correcciones están pendientes de diseño y prueba.

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

## Arquitectura objetivo

La arquitectura objetivo procesa detecciones globales **VIIRS de NOAA-20 y NOAA-21** publicadas por NASA FIRMS. En esta primera etapa se prepara la infraestructura local reproducible; el consumidor, los jobs analíticos y la visualización se implementarán en fases posteriores.

### Flujo de Datos
1. **Ingesta (Consumidor Python):** Un servicio consulta periódicamente los lotes CSV de la API de NASA FIRMS (combinando sensores para sostener un caudal promedio $\ge 1$ evento/segundo) e inserta los eventos crudos directamente en MongoDB como estado de verdad operativa.
2. **Capa Operativa y Seguridad (MongoDB):** Clúster distribuido en Docker con **sharding y replicación** (priorizando **CP** según el teorema CAP). Cuenta con índices geoespaciales (`2dsphere`) y temporales para consultas de baja latencia, control de accesos basado en roles (**RBAC** con usuarios independientes por servicio), autenticación interna mediante `keyFile`, aislamiento en red privada y gestión de credenciales con `.env`.
3. **Procesamiento y Enriquecimiento (Apache Spark):** Jobs distribuidos que leen los eventos crudos desde MongoDB para eliminar duplicados, normalizar marcas de tiempo (ISO-8601) y coordenadas (GeoJSON), y enriquecer cada detección cruzándola espacialmente con datasets estáticos (países/regiones, áreas naturales protegidas y volcanes/zonas industriales).
4. **Capa Analítica (OLAP):** Los datos limpios y enriquecidos se almacenan como archivos Parquet en MinIO, compatible con la API S3, para ejecutar consultas analíticas complejas y garantizar la trazabilidad completa del ciclo de vida del dato.
5. **Visualización en Tiempo Real:** Un backend escucha las inserciones en MongoDB mediante **Change Streams** y transmite los eventos nuevos vía **SSE/WebSockets** hacia un mapa interactivo con aceleración WebGL (**MapLibre GL JS + Deck.gl**), permitiendo monitorear intensidad (`FRP`), filtros de confianza y evolución temporal sin recargar la página.

## Entorno local reproducible

### Requisitos

- Windows con Docker Desktop configurado para contenedores Linux, o Docker Engine con Docker Compose v2.
- `uv` para Python 3.12.
- Asignar recursos suficientes a Docker: la topología local incluye tres config servers, seis nodos de datos MongoDB, un router, Spark master/worker y MinIO.

### Preparación

Elige los comandos de tu terminal. Los bloques de PowerShell se usan en PowerShell; los bloques Bash funcionan en Linux/macOS y en zsh. Desde zsh, el script Bash se puede ejecutar con `bash scripts/prepare-env.sh`.

#### PowerShell

1. Generar o completar las credenciales locales sin reemplazar variables ya existentes:

   ```powershell
   .\scripts\prepare-env.ps1
   ```

2. Crear el entorno virtual e instalar las dependencias fijadas en `uv.lock`:

   ```powershell
   uv sync --locked
   ```

3. Descargar las imágenes fijadas en Compose e iniciar los servicios:

   ```powershell
   docker compose pull
   docker compose up -d
   ```

#### Bash (Linux/macOS/zsh)

1. Generar o completar las credenciales locales sin reemplazar variables ya existentes:

   ```bash
   bash scripts/prepare-env.sh
   ```

   El script requiere Python 3.12 o posterior disponible como `python3`. Crea `.env` si falta o agrega las variables de infraestructura ausentes, genera contraseñas aleatorias para MongoDB y MinIO, y conserva los valores que ya existían. Agrega `MAP_KEY` manualmente a `.env` si usarás el consumidor FIRMS; no se necesita para iniciar la infraestructura.

2. Crear el entorno virtual e instalar las dependencias fijadas en `uv.lock`:

   ```bash
   uv sync --locked
   ```

3. Descargar las imágenes fijadas en Compose e iniciar los servicios:

   ```bash
   docker compose pull
   docker compose up -d
   ```

En ambas plataformas, la primera ejecución inicializa automáticamente las tres replica sets (config servers y dos shards), registra ambos shards en `mongos` y crea el bucket `firms-analytics` en MinIO.

### Servicios locales

| Servicio | Dirección desde el host | Función |
| --- | --- | --- |
| MongoDB `mongos` | `localhost:27017` (usuario y contraseña de `.env`, autenticación en `admin`) | Router hacia dos shards replicados (tres miembros de datos por shard). |
| MinIO API | `http://localhost:9000` | Almacenamiento de objetos compatible con S3 para Parquet. |
| MinIO Console | `http://localhost:9001` | Consola local para inspeccionar el bucket analítico. |
| Spark master UI | `http://localhost:8080` | Estado del clúster de procesamiento. |
| Spark worker UI | `http://localhost:8081` | Estado del worker local. |

Las interfaces se enlazan a `localhost`; las credenciales están en `.env`. El keyfile de autenticación interna de MongoDB se genera dentro de un volumen Docker y no se guarda en el repositorio. Los datos persisten en volúmenes nombrados; `docker compose down` detiene los servicios y conserva los datos.

Para revisar el estado y la inicialización:

```powershell
docker compose ps
docker compose logs mongo-config-init mongo-shard1-init mongo-shard2-init mongo-add-shards minio-init
```

El Compose fija versiones de MongoDB, Spark y MinIO. Para MinIO usa `dappros/minio`, una copia espejo de terceros, porque los repositorios oficiales ya no permitieron completar pulls anónimos desde esta instalación. El inicializador crea el bucket mediante la API S3 con Python estándar, sin depender de la imagen `mc`. La imagen de MinIO es un espejo no oficial; esta configuración es para desarrollo local del proyecto, no una recomendación de despliegue productivo.

Esta etapa no incluye todavía el consumidor de FIRMS, los jobs Spark de limpieza/enriquecimiento ni el backend y mapa. Por ello, iniciar los contenedores no equivale a demostrar el caudal de la fuente, la carga de datos ni las cinco consultas analíticas.
## Caudal y viabilidad del requisito de stream

La rúbrica exige un promedio mínimo de **1 evento por segundo** y permite combinar fuentes. En una revisión previa comunicada por el equipo, para el **8 de noviembre de 2026** a escala mundial se reportaron **119 498 detecciones VIIRS NOAA-20 y NOAA-21**, equivalentes a aproximadamente **1,38 detecciones por segundo** en ese día; al añadir MODIS se reportaron **131 462 detecciones**, aproximadamente **1,52 por segundo**. Son antecedentes de una sola fecha, **no mediciones reproducidas en este repositorio ni garantía de caudal sostenido, entrega uniforme o eventos nuevos en cada segundo**. Se medirá el volumen en varios días, separado por producto, y se registrará tanto el caudal de detecciones únicas como el de eventos realmente ingresados sin pérdida. También se consultará al profesor si acepta el esquema de consulta periódica y emisión de eventos como stream del proyecto.

## Consideraciones éticas y limitaciones

Las detecciones pueden omitirse por nubosidad, humo, cobertura vegetal, tamaño o duración del fuego, e incluir otras anomalías o artefactos. Las diferencias de resolución, latencia, cobertura y confianza entre productos impiden comparar recuentos o potencia radiativa como si representaran automáticamente número de incendios, daños o riesgo humano. Las consultas y visualizaciones deben conservar el origen del satélite, el producto, las marcas temporales y la incertidumbre; no se publicarán coordenadas como confirmación de un incendio puntual sin verificación independiente. El uso de los datos respetará la atribución recomendada por [NASA FIRMS](https://www.earthdata.nasa.gov/data/tools/firms/faq).

## Plan de implementación y documentación

1. **Validación de la fuente:** fijar productos y región, capturar encabezados reales, medir varios días de datos y acordar con el profesor el mecanismo de conversión de lotes a eventos.
2. **Infraestructura:** documentar y desplegar una base NoSQL operativa con replicación y sharding, una capa analítica apropiada, control de accesos, diagramas y una justificación explícita en términos de CAP. La infraestructura local usa MongoDB para la capa operacional, Spark para procesamiento y Parquet en MinIO para la capa analítica.
3. **Ingesta:** implementar consulta periódica, deduplicación, manejo de errores, inserción y consultas puntuales; medir caudal, pérdida y recuperación ante fallos.
4. **Procesamiento:** limpiar y tipar datos, enriquecerlos con fuentes estáticas cuando aporte valor, conservar trazabilidad y preparar agregaciones analíticas.
5. **Resultados:** ejecutar al menos cinco consultas analíticas complejas, explicar hallazgos e impacto, y mostrar la evolución desde el CSV crudo hasta la información transformada.

El código, las instrucciones de ejecución, las pruebas, las decisiones de diseño, los diagramas y los resultados se incorporarán a este repositorio conforme se implementen. Hasta entonces, este README documenta **la fuente elegida y el estado preliminar**, no una arquitectura ya desplegada.
