#!/bin/sh
set -e

# Environment variables
PROXY_PORT="${PROXY_PORT:-3333}"
CFG_ROOT="${CFG_ROOT:-/data}"
PROFILES_DIR="$CFG_ROOT/config"
CACHE_DIR="$CFG_ROOT/config_cache"
ACTIVE_PROFILE="$PROFILES_DIR/active_profile.toml"

mkdir -p "$PROFILES_DIR" "$CACHE_DIR"

# Bootstrap minimal profile if missing
if [ ! -f "$ACTIVE_PROFILE" ]; then
  echo "No active_profile.toml found – creating a minimal one."
  cat > "$ACTIVE_PROFILE" <<EOF
server = [{ name = "S1", port = ${PROXY_PORT} }]

target = []

routing = [{ from = ["S1"], goal = [] }]
EOF
fi

# Apply config
echo "Applying configuration via one‑shot configurator…"
/usr/local/bin/farm-proxy \
  configure \
  --http-socket-override localhost:8080 \
  --config-file "$ACTIVE_PROFILE" || true

# Hand off to the long‑lived proxy process
echo "Starting main farm‑proxy service…"
exec /usr/local/bin/farm-proxy \
  run \
  --config-file "$CACHE_DIR/last_used_config.toml"