"""Stage a FIRMS Archive Download file in the project's local data directory."""

from __future__ import annotations

import argparse
import csv
import gzip
import logging
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = PROJECT_ROOT / "data" / "raw" / "firms" / "historic"
LOGGER = logging.getLogger("firms.historic")
SUPPORTED_FORMATS = {(".csv",), (".csv", ".gz"), (".zip",), (".json",), (".geojson",)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Copia a data/raw/firms/historic el archivo obtenido mediante "
            "FIRMS Archive Download y lo nombra con el timestamp de esta ejecución."
        )
    )
    parser.add_argument(
        "--archive-file",
        required=True,
        type=Path,
        help="Ruta del archivo descargado desde el enlace que FIRMS envió por correo.",
    )
    return parser.parse_args()


def validate_archive(path: Path) -> None:
    if not path.is_file():
        raise ValueError(f"No existe el archivo indicado: {path}")
    if path.stat().st_size == 0:
        raise ValueError("El archivo descargado está vacío.")

    suffixes = [suffix.lower() for suffix in path.suffixes]
    if tuple(suffixes) not in SUPPORTED_FORMATS:
        raise ValueError("Formato no soportado. Usa CSV, ZIP, JSON, GeoJSON o CSV comprimido en GZIP.")

    if path.suffix.lower() == ".zip":
        try:
            with zipfile.ZipFile(path) as archive:
                if not any(not member.is_dir() for member in archive.infolist()):
                    raise ValueError("El ZIP no contiene archivos.")
        except zipfile.BadZipFile as exc:
            raise ValueError("El archivo tiene extensión ZIP, pero no es un ZIP válido.") from exc
    elif suffixes[-1] == ".csv" or suffixes[-2:] == [".csv", ".gz"]:
        opener = gzip.open if suffixes[-1] == ".gz" else open
        try:
            with opener(path, "rt", encoding="utf-8-sig", newline="") as source:
                header = next(csv.reader(source), None)
        except (OSError, UnicodeError, csv.Error) as exc:
            raise ValueError("No se pudo leer el encabezado CSV del archivo.") from exc
        normalized = {column.strip().lower() for column in (header or [])}
        if not {"latitude", "longitude"}.issubset(normalized):
            raise ValueError("El CSV no parece contener detecciones FIRMS (faltan latitude/longitude).")


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    started_at = datetime.now(timezone.utc)
    try:
        source = args.archive_file.expanduser().resolve(strict=True)
        validate_archive(source)
        suffix = "".join(source.suffixes).lower()
        timestamp = started_at.strftime("%Y%m%dT%H%M%S.%fZ")
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        destination = OUTPUT_ROOT / f"extraction-{timestamp}{suffix}"
        temporary = destination.with_name(destination.name + ".part")
        shutil.copyfile(source, temporary)
        temporary.replace(destination)
    except (OSError, ValueError) as exc:
        LOGGER.error("No se pudo guardar la descarga: %s", exc)
        return 1

    size_mb = destination.stat().st_size / (1024 * 1024)
    LOGGER.info("Archivo de archivo FIRMS guardado: %s (%.2f MiB)", destination, size_mb)
    return 0


if __name__ == "__main__":
    sys.exit(main())
