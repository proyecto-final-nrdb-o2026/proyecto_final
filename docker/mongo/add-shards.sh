#!/usr/bin/env bash
set -euo pipefail

ROOT_USER="${MONGO_ROOT_USER:?MONGO_ROOT_USER es requerido}"
ROOT_PASSWORD="${MONGO_ROOT_PASSWORD:?MONGO_ROOT_PASSWORD es requerido}"

attempts=0
until mongosh --host mongo-router:27017 --quiet --eval 'db.hello().ok' 2>/dev/null | grep -q '^1$'; do
  attempts=$((attempts + 1))
  if [ "$attempts" -ge 90 ]; then
    echo 'mongos no respondió a tiempo' >&2
    exit 1
  fi
  sleep 2
done

mongosh --host mongo-router:27017 \
  --username "$ROOT_USER" \
  --password "$ROOT_PASSWORD" \
  --authenticationDatabase admin \
  --quiet --eval '
    const known = db.adminCommand({ listShards: 1 }).shards.map((shard) => shard._id);
    if (!known.includes("shard1RS")) {
      sh.addShard("shard1RS/shard1-1:27017,shard1-2:27017,shard1-3:27017");
    }
    if (!known.includes("shard2RS")) {
      sh.addShard("shard2RS/shard2-1:27017,shard2-2:27017,shard2-3:27017");
    }
    printjson(db.adminCommand({ listShards: 1 }));
  '

echo 'MongoDB sharded cluster is initialized.'
