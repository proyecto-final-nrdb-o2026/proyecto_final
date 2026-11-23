"""Poll FIRMS for recent VIIRS detections and append newly seen rows to CSV."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import logging
import os
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne
from pymongo.errors import PyMongoError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = PROJECT_ROOT / "data" / "raw" / "firms" / "actual"
API_ROOT = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
PRODUCTS = {
    "VIIRS_NOAA20_NRT": "NOAA-20",
    "VIIRS_NOAA21_NRT": "NOAA-21",
}
REQUIRED_COLUMNS = {"latitude", "longitude", "acq_date", "acq_time", "satellite"}
FINGERPRINT_TTL_SECONDS = 48 * 60 * 60
LOGGER = logging.getLogger("firms.actual")


class PollError(RuntimeError):
    """A sanitized API, CSV, or schema error."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Consulta FIRMS cada minuto e inserta detecciones nuevas en MongoDB."
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=60.0,
        help="Intervalo entre inicios de consulta (por defecto: 60 segundos).",
    )
    parser.add_argument(
        "--area",
        default="world",
        help="Área FIRMS (world o west,south,east,north; por defecto: world).",
    )
    return parser.parse_args()


def session_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def make_output_fields(header: list[str]) -> list[str]:
    lookup = {name.strip().lower(): name for name in header}
    if not REQUIRED_COLUMNS.issubset(lookup):
        raise PollError("La respuesta de FIRMS no contiene las columnas VIIRS esperadas.")
    date_col = lookup["acq_date"]
    time_col = lookup["acq_time"]
    date_index = header.index(date_col)
    fields = [name for name in header if name not in {date_col, time_col}]
    fields.insert(min(date_index, len(fields)), "acq_datetime_utc")
    return fields


def parse_acquisition_time(row: dict[str, str], header: list[str]) -> str:
    lookup = {name.strip().lower(): name for name in header}
    acquired_date = row.get(lookup["acq_date"], "").strip()
    acquired_time = row.get(lookup["acq_time"], "").strip()
    if not acquired_time.isdigit() or len(acquired_time) > 4:
        raise ValueError("acq_time no tiene formato HHMM")
    parsed = datetime.strptime(
        f"{date.fromisoformat(acquired_date).isoformat()}{acquired_time.zfill(4)}",
        "%Y-%m-%d%H%M",
    ).replace(tzinfo=timezone.utc)
    return parsed.isoformat(timespec="minutes").replace("+00:00", "Z")


def parse_csv(content: str) -> tuple[list[str], list[dict[str, str]]]:
    try:
        reader = csv.DictReader(io.StringIO(content, newline=""))
        header = reader.fieldnames or []
        normalized = {name.strip().lower() for name in header}
        if not REQUIRED_COLUMNS.issubset(normalized):
            raise PollError("La respuesta no parece un CSV de detecciones VIIRS de FIRMS.")
        rows = [dict(row) for row in reader if row and None not in row]
        return header, rows
    except (csv.Error, UnicodeError) as exc:
        raise PollError("No se pudo interpretar la respuesta CSV de FIRMS.") from exc


def fetch_product(client: httpx.Client, map_key: str, product: str, area: str):
    # A one-day rolling window limits repeated global queries and catches late same-day updates.
    url = f"{API_ROOT}/{map_key}/{product}/{area}/1"
    for attempt in range(1, 4):
        try:
            response = client.get(url)
        except httpx.TransportError as exc:
            if attempt == 3:
                raise PollError("Fallo de transporte al consultar FIRMS.") from exc
            time.sleep(attempt * 2)
            continue

        if response.status_code == 429 or response.status_code >= 500:
            if attempt == 3:
                raise PollError(f"FIRMS respondió HTTP {response.status_code} tras varios intentos.")
            retry_after = response.headers.get("Retry-After", "")
            wait_seconds = int(retry_after) if retry_after.isdigit() else attempt * 2
            time.sleep(min(wait_seconds, 30))
            continue
        if response.status_code >= 400:
            raise PollError(f"FIRMS respondió HTTP {response.status_code}; revisa MAP_KEY y los parámetros.")
        return parse_csv(response.text)
    raise PollError("No fue posible consultar FIRMS.")


def fingerprint(product: str, row: dict[str, str]) -> str:
    stable_row = "\x1f".join(f"{key}={row[key]}" for key in sorted(row))
    return hashlib.sha256(f"{product}\x1e{stable_row}".encode("utf-8")).hexdigest()


def connect_mongo():
    username = os.getenv("MONGO_ROOT_USER", "").strip()
    password = os.getenv("MONGO_ROOT_PASSWORD", "")
    if not username or not password:
        raise ValueError("Define MONGO_ROOT_USER y MONGO_ROOT_PASSWORD en .env.")
    try:
        port = int(os.getenv("MONGO_PORT", "27017"))
    except ValueError as exc:
        raise ValueError("MONGO_PORT debe ser un número de puerto válido.") from exc

    host = os.getenv("MONGO_HOST", "127.0.0.1").strip()
    database_name = os.getenv("MONGO_DATABASE", "firms").strip() or "firms"
    collection_name = os.getenv("MONGO_COLLECTION", "events").strip() or "events"
    client = MongoClient(
        host=host,
        port=port,
        username=username,
        password=password,
        authSource="admin",
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
    )
    try:
        client.admin.command("ping")
    except PyMongoError:
        client.close()
        raise
    return client, client[database_name][collection_name], host, port, database_name, collection_name


def transformed_row(row: dict[str, str], header: list[str], fields: list[str]) -> dict[str, str]:
    lookup = {name.strip().lower(): name for name in header}
    result = {name: value or "" for name, value in row.items() if name not in {lookup["acq_date"], lookup["acq_time"]}}
    result["acq_datetime_utc"] = parse_acquisition_time(row, header)
    return {field: result.get(field, "") for field in fields}


def mongo_document(
    product: str,
    key: str,
    output_row: dict[str, str],
) -> dict[str, object]:
    document: dict[str, object] = dict(output_row)
    document["_id"] = key
    document["source_product"] = product
    document["acq_datetime_utc"] = datetime.fromisoformat(
        output_row["acq_datetime_utc"].replace("Z", "+00:00")
    )
    return document


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.interval_seconds <= 0:
        LOGGER.error("--interval-seconds debe ser mayor que cero.")
        return 2

    load_dotenv(PROJECT_ROOT / ".env")
    map_key = os.getenv("MAP_KEY", "").strip()
    if not map_key or map_key == "replace-with-your-firms-map-key":
        LOGGER.error("Define tu clave FIRMS en MAP_KEY dentro de .env.")
        return 2

    try:
        mongo_client, collection, mongo_host, mongo_port, database_name, collection_name = connect_mongo()
    except (ValueError, PyMongoError) as exc:
        LOGGER.error("No se pudo conectar a MongoDB; FIRMS no se consultó: %s", exc)
        return 1

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    filename = f"extraction-{session_timestamp()}.csv"
    output_path = OUTPUT_ROOT / filename
    output_path.touch(exist_ok=False)
    seen: dict[str, float] = {}
    baselined_products: set[str] = set()
    schema: list[str] | None = None
    timeout = httpx.Timeout(connect=20.0, read=180.0, write=30.0, pool=30.0)
    LOGGER.info("Conexión a MongoDB verificada: %s:%s/%s.%s", mongo_host, mongo_port, database_name, collection_name)
    LOGGER.info(
        "Polling iniciado; el primer sondeo de cada producto solo establece la línea base. "
        "Salida CSV: %s; intervalo: %s s",
        output_path,
        args.interval_seconds,
    )

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            while True:
                poll_started = time.monotonic()
                new_rows: list[dict[str, str]] = []
                new_documents: list[dict[str, object]] = []
                event_keys: list[tuple[str, str]] = []
                counts = {product: 0 for product in PRODUCTS}
                baseline_counts = {product: 0 for product in PRODUCTS}
                poll_headers: dict[str, list[str]] = {}
                poll_records: list[tuple[str, list[str], dict[str, str]]] = []

                for product in PRODUCTS:
                    try:
                        header, rows = fetch_product(client, map_key, product, args.area)
                    except PollError as exc:
                        LOGGER.error("Consulta %s falló: %s", PRODUCTS[product], exc)
                        continue
                    poll_headers[product] = header
                    poll_records.extend((product, header, row) for row in rows)

                if poll_headers:
                    # The two VIIRS products normally have the same schema. Form a union
                    # before writing so a column present in either product is retained.
                    combined_header = list(poll_headers.values())[0].copy()
                    for product_header in poll_headers.values():
                        for column in product_header:
                            if column not in combined_header:
                                combined_header.append(column)
                    current_schema = make_output_fields(combined_header)
                    if schema is None:
                        schema = current_schema
                        with output_path.open("w", encoding="utf-8", newline="") as output_file:
                            csv.DictWriter(output_file, fieldnames=schema).writeheader()
                    elif current_schema != schema:
                        raise PollError(
                            "El esquema CSV de FIRMS cambió durante la ejecución; "
                            "se detuvo el proceso para no perder columnas."
                        )

                    now = time.monotonic()
                    for key, first_seen in list(seen.items()):
                        if now - first_seen > FINGERPRINT_TTL_SECONDS:
                            del seen[key]

                    malformed = 0
                    for product, header, row in poll_records:
                        key = fingerprint(product, row)
                        if product not in baselined_products:
                            if key not in seen:
                                seen[key] = now
                                baseline_counts[product] += 1
                            continue
                        if key in seen:
                            continue
                        try:
                            output_row = transformed_row(row, header, schema)
                        except (ValueError, KeyError):
                            malformed += 1
                            continue
                        new_documents.append(mongo_document(product, key, output_row))
                        new_rows.append(output_row)
                        event_keys.append((product, key))
                    baselined_products.update(poll_headers)
                    if malformed:
                        LOGGER.warning("Filas omitidas por fecha/hora inválida: %s", malformed)

                if new_documents:
                    operations = [
                        UpdateOne({"_id": document["_id"]}, {"$setOnInsert": document}, upsert=True)
                        for document in new_documents
                    ]
                    inserted_rows = []
                    try:
                        result = collection.bulk_write(operations, ordered=False)
                    except PyMongoError as exc:
                        LOGGER.error("No se insertaron los eventos de este sondeo en MongoDB: %s", exc.__class__.__name__)
                    else:
                        inserted_indexes = set(result.upserted_ids)
                        for index, (product, key) in enumerate(event_keys):
                            seen[key] = now
                            if index in inserted_indexes:
                                counts[product] += 1
                                inserted_rows.append(new_rows[index])
                    if inserted_rows:
                        with output_path.open("a", encoding="utf-8", newline="") as output_file:
                            csv.DictWriter(output_file, fieldnames=schema).writerows(inserted_rows)

                total = sum(counts.values())
                timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
                print(
                    f"{timestamp} | línea base NOAA-20: {baseline_counts['VIIRS_NOAA20_NRT']} | "
                    f"NOAA-21: {baseline_counts['VIIRS_NOAA21_NRT']} | "
                    f"nuevas NOAA-20: {counts['VIIRS_NOAA20_NRT']} | "
                    f"NOAA-21: {counts['VIIRS_NOAA21_NRT']} | nuevas: {total}",
                    flush=True,
                )
                elapsed = time.monotonic() - poll_started
                time.sleep(max(0.0, args.interval_seconds - elapsed))
    except KeyboardInterrupt:
        LOGGER.info("Polling detenido. Archivo guardado: %s", output_path)
        return 0
    except PollError as exc:
        LOGGER.error("Polling detenido: %s", exc)
        return 1
    finally:
        mongo_client.close()


if __name__ == "__main__":
    sys.exit(main())
