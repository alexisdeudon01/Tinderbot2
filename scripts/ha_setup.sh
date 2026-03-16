#!/usr/bin/env bash
# =============================================================================
# ha_setup.sh — Automatise l'installation complète de Tinder MCP dans HA
#
# Usage : bash scripts/ha_setup.sh
# Prérequis : fichier .env à la racine avec HA_URL et HA_TOKEN
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$ROOT_DIR/.env"

# Charger les variables depuis .env
if [ ! -f "$ENV_FILE" ]; then
    echo "ERREUR : fichier .env introuvable. Crée-le avec HA_URL et HA_TOKEN."
    exit 1
fi
source "$ENV_FILE"

if [ -z "${HA_TOKEN:-}" ] || [ "$HA_TOKEN" = "COLLE_TON_NOUVEAU_TOKEN_ICI" ]; then
    echo "ERREUR : remplis HA_TOKEN dans le fichier .env avant de lancer ce script."
    exit 1
fi

ADDON_REPO="https://github.com/alexisdeudon01/Tinderbot2"
HA_HEADERS=(-H "Authorization: Bearer $HA_TOKEN" -H "Content-Type: application/json")

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

step() { echo -e "\n${BLUE}▶ $1${NC}"; }
ok()   { echo -e "  ${GREEN}✓ $1${NC}"; }
warn() { echo -e "  ${YELLOW}⚠ $1${NC}"; }
err()  { echo -e "  ${RED}✗ $1${NC}"; }

# ---------------------------------------------------------------------------
# 1. Tester la connexion
# ---------------------------------------------------------------------------
step "1/5 — Test de connexion à $HA_URL"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${HA_HEADERS[@]}" "$HA_URL/api/")
if [ "$STATUS" != "200" ]; then
    err "Impossible de joindre HA ($STATUS). Vérifie HA_URL et HA_TOKEN."
    exit 1
fi
HA_VERSION=$(curl -s "${HA_HEADERS[@]}" "$HA_URL/api/" | python3 -c "import sys,json; print(json.load(sys.stdin).get('version','?'))")
ok "Connecté à Home Assistant $HA_VERSION"

# ---------------------------------------------------------------------------
# 2. Ajouter le dépôt add-on via Supervisor
# ---------------------------------------------------------------------------
step "2/5 — Ajout du dépôt add-on dans le Supervisor"
ADD_RESP=$(curl -s -X POST "${HA_HEADERS[@]}" \
    "$HA_URL/api/hassio/store/repositories" \
    -d "{\"repository\": \"$ADDON_REPO\"}" 2>&1)
if echo "$ADD_RESP" | grep -q '"result":"ok"'; then
    ok "Dépôt add-on ajouté"
elif echo "$ADD_RESP" | grep -qi "already\|exist"; then
    warn "Dépôt déjà présent — OK"
else
    warn "Réponse Supervisor : $ADD_RESP"
fi

# ---------------------------------------------------------------------------
# 3. Installer l'add-on Tinder MCP Server
# ---------------------------------------------------------------------------
step "3/5 — Installation de l'add-on Tinder MCP Server"
INSTALL_RESP=$(curl -s -X POST "${HA_HEADERS[@]}" \
    "$HA_URL/api/hassio/addons/tinder_mcp_server/install" 2>&1)
if echo "$INSTALL_RESP" | grep -q '"result":"ok"'; then
    ok "Add-on installé"
    # Démarrer l'add-on
    curl -s -X POST "${HA_HEADERS[@]}" "$HA_URL/api/hassio/addons/tinder_mcp_server/start" > /dev/null
    ok "Add-on démarré sur le port 3000"
elif echo "$INSTALL_RESP" | grep -qi "already\|installed"; then
    warn "Add-on déjà installé"
else
    warn "Réponse : $INSTALL_RESP"
    warn "Lance l'add-on manuellement via Paramètres > Modules complémentaires"
fi

# ---------------------------------------------------------------------------
# 4. Uploader le dashboard Lovelace
# ---------------------------------------------------------------------------
step "4/5 — Création du dashboard Tinder MCP"
DASHBOARD_YAML="$ROOT_DIR/lovelace/tinder_dashboard.yaml"
if [ ! -f "$DASHBOARD_YAML" ]; then
    err "Fichier dashboard introuvable : $DASHBOARD_YAML"
else
    # Vérifier si le dashboard existe déjà
    EXISTING=$(curl -s "${HA_HEADERS[@]}" "$HA_URL/api/lovelace/dashboards" | \
        python3 -c "import sys,json; dbs=json.load(sys.stdin); print(next((d['id'] for d in dbs if d.get('url_path')=='tinder-mcp'), ''))" 2>/dev/null || echo "")

    if [ -n "$EXISTING" ]; then
        warn "Dashboard déjà créé (id=$EXISTING) — mise à jour du contenu"
        DASH_ID="$EXISTING"
    else
        # Créer le dashboard
        CREATE=$(curl -s -X POST "${HA_HEADERS[@]}" \
            "$HA_URL/api/lovelace/dashboards" \
            -d '{"icon":"mdi:fire","title":"Tinder MCP","url_path":"tinder-mcp","show_in_sidebar":true,"require_admin":false,"mode":"yaml"}')
        DASH_ID=$(echo "$CREATE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")
        ok "Dashboard créé (id=$DASH_ID)"
    fi

    # Uploader le YAML du dashboard
    YAML_CONTENT=$(cat "$DASHBOARD_YAML")
    curl -s -X POST "${HA_HEADERS[@]}" \
        "$HA_URL/api/lovelace/config?force" \
        --data-raw "$YAML_CONTENT" > /dev/null
    ok "Contenu du dashboard uploadé"
fi

# ---------------------------------------------------------------------------
# 5. Résumé final
# ---------------------------------------------------------------------------
step "5/5 — Résumé"
echo ""
echo -e "  ${GREEN}Add-on Tinder MCP Server${NC}  → Paramètres > Modules complémentaires"
echo -e "  ${GREEN}Intégration Tinder MCP${NC}    → Paramètres > Appareils et services > + Ajouter"
echo -e "  ${GREEN}Dashboard${NC}                  → $HA_URL/tinder-mcp"
echo ""
echo -e "${YELLOW}Prochaine étape :${NC}"
echo -e "  Paramètres > Appareils et services > + Ajouter > 'Tinder MCP'"
echo -e "  → Entre ton numéro de téléphone → SMS → OTP → Done"
echo ""
