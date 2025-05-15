#!/bin/sh
set -e

if [ ! -f config/config.toml ]; then
  echo "No config/config.toml found; copying example..."
  cp config/config.toml.example config/config.toml
fi

echo "📋 External port mapping: Proxy ${PROXY_PORT:-3331}, Dashboard ${DASHBOARD_PORT:-5000}"

case "$1" in
  proxy)
    echo "🌐 Starting TaoHash proxy (main)…"
    exec python -m src.main
    ;;

  *)
    echo "Usage: $0 {proxy}"
    exit 1
    ;;
esac