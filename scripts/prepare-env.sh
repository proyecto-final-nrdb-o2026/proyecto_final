#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
example_path="$repo_root/.env.example"
env_path="$repo_root/.env"

if [[ ! -f "$example_path" ]]; then
  echo "No se encontró .env.example" >&2
  exit 1
fi

python3 - "$example_path" "$env_path" <<'PY'
import base64
import secrets
import sys
from pathlib import Path

example_path, env_path = map(Path, sys.argv[1:])
example_lines = example_path.read_text(encoding="utf-8").splitlines()
password_names = {"MONGO_ROOT_PASSWORD", "MINIO_ROOT_PASSWORD"}

def random_password():
    return base64.b64encode(secrets.token_bytes(32)).decode("ascii")

def value_for(line):
    name, _, value = line.partition("=")
    if name in password_names:
        return f"{name}={random_password()}"
    return line

if not env_path.exists():
    initial = [value_for(line) for line in example_lines if not line.startswith("MAP_KEY=")]
    env_path.write_text("\n".join(initial) + "\n", encoding="utf-8")
    print("Creé .env con credenciales locales aleatorias. Agrega MAP_KEY manualmente si usarás el consumidor.")
    raise SystemExit(0)

current_lines = env_path.read_text(encoding="utf-8").splitlines()
present = set()
for line in current_lines:
    name, sep, _ = line.partition("=")
    if sep and name and (name[0].isalpha() or name[0] == "_") and all(c.isalnum() or c == "_" for c in name):
        present.add(name)

missing = []
for line in example_lines:
    if line.startswith("#"):
        missing.append(line)
        continue
    name, sep, _ = line.partition("=")
    if not sep or name in present or name == "MAP_KEY":
        continue
    missing.append(value_for(line))
    present.add(name)

if missing:
    with env_path.open("a", encoding="utf-8", newline="\n") as env_file:
        env_file.write("\n# Valores locales agregados por scripts/prepare-env.sh\n")
        env_file.write("\n".join(missing) + "\n")

print("Configuración local lista. Se conservaron las variables que ya existían en .env.")
PY
