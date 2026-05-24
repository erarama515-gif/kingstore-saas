#!/usr/bin/env bash
# =============================================================================
# Kingstore SaaS — emergency stop / restore
# Use:   maintenance-toggle.sh stop      # take demo offline
#        maintenance-toggle.sh start     # bring back online
# =============================================================================
set -euo pipefail

case "${1:-}" in
    stop)
        systemctl stop kingstore-api.service kingstore-web.service
        echo "Kingstore demo is OFFLINE."
        ;;
    start)
        systemctl start kingstore-api.service kingstore-web.service
        sleep 2
        curl -fsS "http://127.0.0.1:8001/api/v1/health" && echo " — API OK"
        echo "Kingstore demo is ONLINE."
        ;;
    *)
        echo "Usage: $0 {stop|start}"
        exit 1
        ;;
esac
