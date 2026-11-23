# Proyecto final: detecciones de incendios y anomalías térmicas con NASA FIRMS

Proyecto del curso **Bases de Datos No Relacionales (Otoño 2026)**. El objetivo es construir y documentar una arquitectura distribuida que convierta detecciones satelitales publicadas por [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/) en datos operativos y analíticos. La infraestructura local y un polling inicial con escritura en MongoDB ya están implementados. El control de accesos, la carga histórica a MongoDB, el análisis con Spark/Parquet y el mapa con retraso de una hora son frentes pendientes.

## Fuente de datos y alcance preliminar

El *Fire Information for Resource Management System* (FIRMS) de NASA distribuye detecciones de fuegos activos y otras anomalías térmicas derivadas de sensores satelitales. Cada fila identifica un píxel donde se detectó una anomalía, con coordenadas, momento de adquisición y mediciones asociadas. **Una detección no equivale necesariamente a un incendio distinto, a su ubicación exacta ni a su superficie quemada**: el punto representa el centro del píxel observado y pueden existir otras fuentes de calor o falsos positivos.

El alcance inicial consulta datos **VIIRS de NOAA-20 y NOAA-21 a escala mundial**; S-NPP y MODIS no se incluyen en esta etapa. NASA FIRMS publica resultados de la API en **lotes CSV**, no mediante un flujo de eventos individual de tipo push. `etl/actual.py` consulta cada minuto, establece una línea base al arrancar, identifica filas nuevas durante esa ejecución y las inserta en MongoDB. La cadencia real de publicación, las correcciones y el caudal sostenido deben medirse.

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

La arquitectura procesa detecciones globales **VIIRS de NOAA-20 y NOAA-21** publicadas por NASA FIRMS. La infraestructura local y la ingesta inicial están disponibles; el resto del flujo se completará en ramas de trabajo coordinadas.

### Flujo de Datos
1. **Ingesta (Python, implementada inicialmente):** `etl/actual.py` consulta NOAA-20/21 NRT cada minuto, omite la línea base inicial y hace upsert de nuevas filas en `firms.events`. Guarda además un CSV con los documentos insertados en esa sesión. La autenticación actual usa el usuario root local; se reemplazará por una cuenta de servicio con privilegios mínimos.
2. **Capa Operativa y Seguridad (MongoDB):** El compose levanta `mongos`, dos shards y sus replica sets. El acceso de usuarios de aplicación con roles independientes (**RBAC**) está pendiente. Índices de consulta, clave de shard y permisos de lectura/escritura se deben acordar con las ramas de ingesta, Spark y mapa antes de aplicarlos.
3. **Procesamiento histórico (Apache Spark, pendiente):** Leerá el archivo entregado por FIRMS Archive Download, normalizará tipos y `acq_date`/`acq_time`, y producirá consultas analíticas. No debe borrar ni modificar el CSV original.
4. **Capa Analítica (Parquet en MinIO, pendiente):** Spark escribirá resultados limpios/enriquecidos como Parquet en el bucket `firms-analytics`; el esquema y la estrategia de particionado deben quedar documentados.
5. **Mapa con retraso de una hora (pendiente):** Un backend consumirá eventos de MongoDB y mostrará puntos en el mapa. Para medir el retraso desde la ingesta con exactitud, los documentos necesitan `ingested_at` UTC; esa marca aún no se guarda en `etl/actual.py` y debe acordarse con la rama de ingesta antes de implementar el filtro de 60 minutos.

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

La extracción histórica deja un archivo de FIRMS en `data/`; el polling reciente inserta eventos en MongoDB y conserva un CSV de la sesión. La carga histórica del archivo a MongoDB, los jobs Spark de limpieza/enriquecimiento y el backend y mapa siguen pendientes. Iniciar los contenedores o extraer datos no demuestra por sí mismo el caudal de la fuente ni las cinco consultas analíticas.
### Extracción histórica de FIRMS

`etl/historic.py` coloca en `data/raw/firms/historic/` el archivo obtenido con **FIRMS Archive Download** y lo nombra `extraction-<timestamp-UTC>.<extensión>`. La salida local de `data/` está excluida de Git.

La orden de archivo se solicita manualmente en [FIRMS Archive Download](https://firms.modaps.eosdis.nasa.gov/download/): selecciona los productos NOAA-20 y NOAA-21, área mundial, el intervalo de fechas requerido y CSV. FIRMS procesa la solicitud y envía por correo el enlace para descargarla. Guarda el archivo descargado localmente y luego pásale la ruta al script:

```bash
uv run python etl/historic.py --archive-file "/ruta/al/archivo_firms.csv"
```

En PowerShell, por ejemplo:

```powershell
uv run python etl/historic.py --archive-file "C:\Users\usuario\Downloads\archivo_firms.csv"
```

El script valida que el CSV tenga columnas de coordenadas (o que el ZIP sea legible), copia el archivo sin transformar sus registros y conserva su extensión. FIRMS no documenta una API pública para automatizar el envío de esta orden; por eso la solicitud y descarga iniciales son manuales. Esta etapa no normaliza ni inserta todavía los datos en MongoDB. [Archivo FIRMS](https://firms.modaps.eosdis.nasa.gov/download/).

### Polling de datos recientes

`etl/actual.py` primero verifica la conexión con MongoDB (`MONGO_HOST`, `MONGO_PORT`, usuario/contraseña de `.env`, autenticación en `admin`). Si Mongo responde, consulta cada minuto los productos NRT de NOAA-20 y NOAA-21 en el área mundial. El primer sondeo de cada producto solo establece la línea base y descarta las detecciones que ya estaban publicadas; después inserta en `firms.events` las filas nuevas con `acq_date` + `acq_time` combinados en `acq_datetime_utc` UTC. El `_id` determinista evita duplicar una fila idéntica si se reinicia el proceso. También conserva en CSV los eventos efectivamente insertados en `data/raw/firms/actual/extraction-<inicio-UTC>.csv`. La consola informa la línea base del primer sondeo y, después, los conteos de inserciones por satélite.

Con `MAP_KEY` configurada en `.env`, inicia el polling desde la raíz del proyecto:

```bash
uv run python etl/actual.py
```

Detén con `Ctrl+C`. Para cambiar el intervalo o el área, consulta `uv run python etl/actual.py --help`. La línea base vive en memoria y se vuelve a establecer al reiniciar. MongoDB usa un `_id` determinista derivado de la fila y el producto para evitar duplicados entre ejecuciones; si cambia cualquier campo de origen, se guarda como un documento distinto. La consola cuenta inserciones nuevas en MongoDB.

## Caudal y viabilidad del requisito de stream

La rúbrica exige un promedio mínimo de **1 evento por segundo** y permite combinar fuentes. En una revisión previa comunicada por el equipo, para el **8 de noviembre de 2026** a escala mundial se reportaron **119 498 detecciones VIIRS NOAA-20 y NOAA-21**, equivalentes a aproximadamente **1,38 detecciones por segundo** en ese día; al añadir MODIS se reportaron **131 462 detecciones**, aproximadamente **1,52 por segundo**. Son antecedentes de una sola fecha, **no mediciones reproducidas en este repositorio ni garantía de caudal sostenido, entrega uniforme o eventos nuevos en cada segundo**. Se medirá el volumen en varios días, separado por producto, y se registrará tanto el caudal de detecciones únicas como el de eventos realmente ingresados sin pérdida. También se consultará al profesor si acepta el esquema de consulta periódica y emisión de eventos como stream del proyecto.

## Consideraciones éticas y limitaciones

Las detecciones pueden omitirse por nubosidad, humo, cobertura vegetal, tamaño o duración del fuego, e incluir otras anomalías o artefactos. Las diferencias de resolución, latencia, cobertura y confianza entre productos impiden comparar recuentos o potencia radiativa como si representaran automáticamente número de incendios, daños o riesgo humano. Las consultas y visualizaciones deben conservar el origen del satélite, el producto, las marcas temporales y la incertidumbre; no se publicarán coordenadas como confirmación de un incendio puntual sin verificación independiente. El uso de los datos respetará la atribución recomendada por [NASA FIRMS](https://www.earthdata.nasa.gov/data/tools/firms/faq).

## Plan de implementación y documentación

1. **Validación de la fuente:** fijar productos y región, capturar encabezados reales, medir varios días de datos y acordar con el profesor el mecanismo de conversión de lotes a eventos.
2. **Infraestructura:** documentar y desplegar una base NoSQL operativa con replicación y sharding, una capa analítica apropiada, control de accesos, diagramas y una justificación explícita en términos de CAP. La infraestructura local usa MongoDB para la capa operacional, Spark para procesamiento y Parquet en MinIO para la capa analítica.
3. **Ingesta:** el polling y el upsert inicial están implementados. Falta una cuenta de servicio de privilegios mínimos, el marcador **ingested_at**, manejo de revisiones, métricas persistentes y evaluación de pérdida/recuperación.
4. **Procesamiento:** falta cargar el archivo histórico en Spark, normalizar y tipar los datos, producir Parquet en MinIO y conservar trazabilidad.
5. **Visualización:** falta el mapa y acordar el filtro de una hora usando una marca de tiempo explícita.
6. **Resultados:** ejecutar al menos cinco consultas analíticas complejas, explicar hallazgos e impacto, y mostrar la evolución desde el CSV crudo hasta la información transformada.

El código, las instrucciones, las decisiones de diseño, los diagramas y los resultados se incorporarán a este repositorio conforme se implementen. Este README distingue entre infraestructura local disponible, ingesta inicial y componentes aún pendientes.

## Anexo: recomendaciones para trabajar en ramas e integrar cambios

### Ramas y responsabilidad

Partan de la misma versión actualizada de main y asignen una persona responsable por componente:

| Rama sugerida | Responsable | Alcance principal |
| --- | --- | --- |
| **feature/mongo-rbac** | Control de accesos | Usuarios/roles de aplicación, inicialización segura, variables de entorno y conexión del consumidor con el usuario de ingesta. |
| **feature/mapa-delay-1h** | Mapa | Servicio/API del mapa, conexión Mongo de solo lectura, interfaz y política de retraso de una hora. |
| **feature/spark-historico-parquet** | Análisis histórico | Lectura del archivo bajo **data/raw/firms/historic/**, procesamiento Spark, consultas y salida Parquet en MinIO. |

Antes de crear las ramas, integren y hagan commit en main del estado actual de este repositorio, incluidos los nuevos scripts y documentación. Mantengan la edición del README a cargo de una sola persona de integración. La rama RBAC será responsable de docker-compose.yaml y de los scripts de inicialización Mongo; las demás ramas deben pedirle los cambios que necesiten en esos archivos. Si un componente necesita cambios compartidos, acuerden el contrato y el archivo responsable antes de editarlo. Agreguen documentación específica por componente en docs/ para evitar que varias ramas reescriban el README a la vez. No agreguen .env, archivos históricos ni resultados generados: data/ y los secretos locales están excluidos de Git.

### Contratos compartidos

- **MongoDB:** el router local es localhost:27017; la base y colección actuales son firms.events. En Compose los servicios usan mongo-router:27017.
- **Documento actual:** _id es un SHA-256 determinista de la fila original y el producto FIRMS; source_product contiene VIIRS_NOAA20_NRT o VIIRS_NOAA21_NRT; acq_datetime_utc es una fecha BSON UTC. Los demás campos FIRMS se guardan por ahora como cadenas. Una fila corregida con cambios de contenido obtiene otro _id.
- **Seguridad:** el consumidor actual conecta con credenciales root locales. La rama RBAC debe definir nombres de variables y roles de servicio, y coordinar el cambio de etl/actual.py para que escriba con el usuario de ingesta. El mapa debe tener solo lectura; no compartan las credenciales root con servicios.
- **Retraso del mapa:** el documento todavía no tiene ingested_at. Antes de bifurcar, acuerden si la persona de integración hará un commit pequeño en etl/actual.py para agregar esa marca UTC, o si la rama de RBAC la incluirá junto con la conexión del consumidor. Para retrasar desde la recepción, el filtro será ingested_at <= now - 1 hour. No sustituyan esta marca por acq_datetime_utc: son momentos distintos. Si la intención era retrasar una hora desde la observación satelital, documenten esa semántica antes de fijar el filtro.
- **Histórico y Spark:** etl/historic.py coloca el archivo original en data/raw/firms/historic/; los nombres incluyen un timestamp. El Spark job debe aceptar esa ruta como entrada, preservar el original y documentar esquema, campos derivados, particiones y ubicación de salida bajo el bucket firms-analytics. El Compose Spark actual no monta data/; para ejecutar dentro de Docker habrá que acordar un volumen o un mecanismo de entrega del archivo.
- **Esquema analítico:** antes de mergear, acuerden nombres/tipos de campos, columnas particionadas de Parquet, comportamiento ante correcciones y si el mapa lee directamente Mongo o una API intermedia.

### Orden de integración recomendado

1. Fusionar primero feature/mongo-rbac, porque define las credenciales y permisos que usarán los otros servicios.
2. Integrar feature/spark-historico-parquet usando el contrato de entrada/salida acordado y las credenciales de lectura necesarias.
3. Integrar feature/mapa-delay-1h después de que exista el rol de lectura y el campo ingested_at.
4. Después de cada merge, actualizar las otras ramas con main, resolver conflictos en una sola rama responsable y volver a comprobar que el compose y los contratos siguen consistentes.

Ejemplo de creación de rama desde una copia actualizada (asume un remoto llamado origin):

~~~bash
git switch main
git pull --ff-only
git switch -c feature/mongo-rbac
git push -u origin feature/mongo-rbac
~~~

Cada responsable trabaja y sube solo su rama. Antes de abrir la solicitud de merge, debe actualizarla contra el main ya integrado (por ejemplo, git fetch origin y git rebase origin/main), revisar el diff y confirmar que no incluye secretos ni datos locales. Fusionen una rama a la vez para poder localizar conflictos. Después de cada merge, los responsables restantes actualizan su rama y vuelven a comprobar sus contratos.

Orden sugerido: RBAC primero; luego Spark histórico; mapa al final, cuando existan el rol de lectura y ingested_at. La persona de integración puede fusionar cada rama con una solicitud de revisión o con:

~~~bash
git switch main
git pull --ff-only
git merge --no-ff origin/feature/mongo-rbac
git push origin main
~~~

Después de cada integración, comprueben conexión/autorización Mongo, la lectura del CSV histórico, la escritura Parquet en MinIO y que el mapa realmente oculte eventos hasta cumplir el retraso acordado.
