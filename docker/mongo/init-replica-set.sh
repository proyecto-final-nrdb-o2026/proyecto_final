#!/usr/bin/env bash
set -euo pipefail

REPLICA_SET_NAME="${REPLICA_SET_NAME:?REPLICA_SET_NAME es requerido}"
REPLICA_SET_CONFIG="${REPLICA_SET_CONFIG:?REPLICA_SET_CONFIG es requerido}"
REPLICA_SET_SEEDS="${REPLICA_SET_SEEDS:?REPLICA_SET_SEEDS es requerido}"

mongo_local() {
  mongosh --host localhost:27017 --quiet --eval "$1"
}

mongo_authenticated() {
  mongosh --host localhost:27017 \
    --username "$MONGO_ROOT_USER" \
    --password "$MONGO_ROOT_PASSWORD" \
    --authenticationDatabase admin \
    --quiet --eval "$1"
}

attempts=0
until mongo_local 'db.hello().ok' 2>/dev/null | grep -q '^1$'; do
  attempts=$((attempts + 1))
  if [ "$attempts" -ge 90 ]; then
    echo "MongoDB no respondió a tiempo para $REPLICA_SET_NAME" >&2
    exit 1
  fi
  sleep 2
done

authenticated=false
if [ -n "${MONGO_ROOT_USER:-}" ] && mongo_authenticated 'db.adminCommand({ ping: 1 }).ok' >/dev/null 2>&1; then
  authenticated=true
fi

# With keyfile authorization enabled, the localhost exception only lets the
# first administrator be created. Do this while the node is still standalone.
if [ "$authenticated" != 'true' ] && [ "${CREATE_ROOT_USER:-false}" = 'true' ]; then
  : "${MONGO_ROOT_USER:?MONGO_ROOT_USER es requerido}"
  : "${MONGO_ROOT_PASSWORD:?MONGO_ROOT_PASSWORD es requerido}"
  mongo_local '
    db.getSiblingDB("admin").createUser({
      user: process.env.MONGO_ROOT_USER,
      pwd: process.env.MONGO_ROOT_PASSWORD,
      roles: [{ role: "root", db: "admin" }],
    });
  ' >/dev/null
  authenticated=true
fi

if [ "$authenticated" = 'true' ]; then
  initialized="$(mongo_authenticated 'try { rs.status().ok } catch (e) { 0 }' 2>/dev/null | tail -n 1 || true)"
else
  initialized="$(mongo_local 'try { rs.status().ok } catch (e) { 0 }' 2>/dev/null | tail -n 1 || true)"
fi

if [ "$initialized" != '1' ]; then
  if [ "$authenticated" = 'true' ]; then
    mongo_authenticated "rs.initiate(JSON.parse(process.env.REPLICA_SET_CONFIG))" >/dev/null
  else
    mongo_local "rs.initiate(JSON.parse(process.env.REPLICA_SET_CONFIG))" >/dev/null
  fi

  attempts=0
  until mongo_local 'db.hello().isWritablePrimary ? 1 : 0' 2>/dev/null | grep -q '^1$'; do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge 90 ]; then
      echo "No se eligió un primario a tiempo para $REPLICA_SET_NAME" >&2
      exit 1
    fi
    sleep 2
  done
fi

if [ -n "${REPLICA_SET_MEMBERS:-}" ]; then
  add_members_js='
    const existing = rs.conf().members.map((member) => member.host);
    for (const host of process.env.REPLICA_SET_MEMBERS.split(",").filter(Boolean)) {
      if (!existing.includes(host)) rs.add(host);
    }
  '
  if [ "$authenticated" = 'true' ]; then
    mongo_authenticated "$add_members_js" >/dev/null
  else
    mongo_local "$add_members_js" >/dev/null
  fi

  expected=$(( $(printf '%s' "$REPLICA_SET_MEMBERS" | awk -F, '{print NF}') + 1 ))
  attempts=0
  while :; do
    if [ "$authenticated" = 'true' ]; then
      members="$(mongo_authenticated 'rs.status().members.length' 2>/dev/null | tail -n 1 || true)"
    else
      members="$(mongo_local 'rs.status().members.length' 2>/dev/null | tail -n 1 || true)"
    fi
    if [ "${members:-0}" -ge "$expected" ]; then break; fi
    attempts=$((attempts + 1))
    if [ "$attempts" -ge 90 ]; then
      echo "No se unieron todos los miembros de $REPLICA_SET_NAME" >&2
      exit 1
    fi
    sleep 2
  done
fi

echo "Replica set $REPLICA_SET_NAME is ready."