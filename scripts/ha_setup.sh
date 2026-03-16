#!/usr/bin/env bash
# =============================================================================
# ha_setup.sh — Automatise l'installation complète de Tinder MCP dans HAOS
#
# À lancer depuis le Terminal add-on de Home Assistant (pas depuis PC externe)
#
# Usage : bash scripts/ha_setup.sh
# Prérequis : fichier .env à la racine avec HA_URL et HA_TOKEN
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$ROOT_DIR/.env"

# Charger .env
if [ -f "$ENV_FILE" ]; then
    source "$ENV_FILE"
fi

HA_URL="${HA_URL:-http://homeassistant:8123}"
HA_TOKEN="${HA_TOKEN:-}"
ADDON_REPO="https://github.com/alexisdeudon01/Tinderbot2"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

step() { echo -e "\n${BLUE}▶ $1${NC}"; }
ok()   { echo -e "  ${GREEN}✓ $1${NC}"; }
warn() { echo -e "  ${YELLOW}⚠ $1${NC}"; }
err()  { echo -e "  ${RED}✗ $1${NC}"; }

# ---------------------------------------------------------------------------
# 1. Tester la connexion HA
# ---------------------------------------------------------------------------
step "1/5 — Test de connexion à $HA_URL"

if [ -z "$HA_TOKEN" ] || [ "$HA_TOKEN" = "COLLE_TON_NOUVEAU_TOKEN_ICI" ]; then
    err "HA_TOKEN manquant dans .env — requis pour les étapes dashboard"
    echo -e "     Continue quand même pour les étapes qui n'en ont pas besoin..."
    SKIP_API=true
else
    SKIP_API=false
fi

if ! $SKIP_API; then
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer $HA_TOKEN" "$HA_URL/api/" 2>/dev/null || echo "000")
    if [ "$STATUS" = "200" ]; then
        HA_VERSION=$(curl -s -H "Authorization: Bearer $HA_TOKEN" "$HA_URL/api/config" \
            | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('version','?'))" 2>/dev/null || echo "?")
        ok "Connecté à Home Assistant $HA_VERSION"
    else
        warn "Réponse HTTP $STATUS — vérifie HA_URL et HA_TOKEN"
        SKIP_API=true
    fi
fi

# ---------------------------------------------------------------------------
# 2. Ajouter le dépôt add-on via CLI ha (disponible dans le terminal HAOS)
# ---------------------------------------------------------------------------
step "2/5 — Ajout du dépôt add-on"

if command -v ha &> /dev/null; then
    # CLI ha disponible (Terminal HAOS)
    if ha store repositories add "$ADDON_REPO" 2>&1 | grep -qi "ok\|added\|already"; then
        ok "Dépôt ajouté via CLI ha"
    else
        RESULT=$(ha store repositories add "$ADDON_REPO" 2>&1 || true)
        if echo "$RESULT" | grep -qi "exists\|already"; then
            warn "Dépôt déjà présent — OK"
        else
            warn "Résultat : $RESULT"
        fi
    fi
else
    warn "CLI 'ha' non disponible (normal si lancé hors HAOS terminal)"
    warn "Dans HAOS Terminal, exécute manuellement :"
    echo -e "     ${YELLOW}ha store repositories add $ADDON_REPO${NC}"
fi

# ---------------------------------------------------------------------------
# 3. Installer l'add-on via CLI ha
# ---------------------------------------------------------------------------
step "3/5 — Installation de l'add-on Tinder MCP Server"

if command -v ha &> /dev/null; then
    echo "  Installation en cours (peut prendre 2-3 min, Docker build Node.js)..."
    if ha addons install local_tinder_mcp_server 2>&1 | grep -qi "ok\|installed"; then
        ok "Add-on installé"
        ha addons start local_tinder_mcp_server 2>/dev/null && ok "Add-on démarré (port 3000)" || warn "Démarre-le manuellement dans Paramètres > Add-ons"
    else
        RESULT=$(ha addons install local_tinder_mcp_server 2>&1 || true)
        warn "Résultat : $RESULT"
        warn "Lance-le manuellement : Paramètres > Modules complémentaires > Tinder MCP Server"
    fi
else
    warn "CLI 'ha' non disponible — installe l'add-on manuellement"
fi

# ---------------------------------------------------------------------------
# 4. Copier les fichiers custom_components dans /config/
# ---------------------------------------------------------------------------
step "4/5 — Copie de l'intégration dans /config/custom_components/"

CONFIG_DIR="/config"
if [ -d "$CONFIG_DIR" ]; then
    mkdir -p "$CONFIG_DIR/custom_components"
    cp -r "$ROOT_DIR/custom_components/tinder_mcp" "$CONFIG_DIR/custom_components/"
    ok "custom_components/tinder_mcp copié dans /config/"

    # Copier le dashboard Lovelace
    mkdir -p "$CONFIG_DIR/dashboards"
    cp "$ROOT_DIR/lovelace/tinder_dashboard.yaml" "$CONFIG_DIR/dashboards/tinder_mcp.yaml"
    ok "Dashboard copié dans /config/dashboards/tinder_mcp.yaml"

    # Ajouter le dashboard dans configuration.yaml si pas déjà présent
    CONF_YAML="$CONFIG_DIR/configuration.yaml"
    if ! grep -q "tinder-mcp" "$CONF_YAML" 2>/dev/null; then
        cat >> "$CONF_YAML" <<'EOF'

# Tinder MCP Dashboard
lovelace:
  dashboards:
    tinder-mcp:
      mode: yaml
      title: Tinder MCP
      icon: mdi:fire
      show_in_sidebar: true
      filename: dashboards/tinder_mcp.yaml
EOF
        ok "Dashboard enregistré dans configuration.yaml"
    else
        warn "Dashboard déjà dans configuration.yaml"
    fi
else
    warn "/config/ non accessible — tu n'es probablement pas dans le terminal HAOS"
    warn "Copie manuellement custom_components/tinder_mcp/ dans ton /config/custom_components/"
fi

# ---------------------------------------------------------------------------
# 5. Redémarrer HA via API pour prendre en compte les changements
# ---------------------------------------------------------------------------
step "5/5 — Redémarrage de Home Assistant"

if ! $SKIP_API; then
    echo "  Redémarrage dans 3 secondes..."
    sleep 3
    curl -s -X POST \
        -H "Authorization: Bearer $HA_TOKEN" \
        "$HA_URL/api/services/homeassistant/restart" > /dev/null 2>&1 && \
        ok "Redémarrage lancé — HA sera de retour dans ~30 secondes" || \
        warn "Lance le redémarrage manuellement : Paramètres > Système > Redémarrer"
else
    warn "Pas de token — redémarre HA manuellement : Paramètres > Système > Redémarrer"
fi

# ---------------------------------------------------------------------------
# Résumé
# ---------------------------------------------------------------------------
echo ""
echo -e "${BLUE}════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Tinder MCP — Installation terminée${NC}"
echo -e "${BLUE}════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${GREEN}Add-on${NC}         Paramètres > Modules complémentaires"
echo -e "  ${GREEN}Intégration${NC}    Paramètres > Appareils et services > + Ajouter > Tinder MCP"
echo -e "  ${GREEN}Dashboard${NC}      $HA_URL/tinder-mcp"
echo ""
echo -e "${YELLOW}Configuration :${NC}"
echo -e "  1. Paramètres > Appareils et services > + Ajouter > 'Tinder MCP'"
echo -e "  2. Entre ton numéro de téléphone"
echo -e "  3. Reçois le SMS Tinder → entre le code OTP"
echo -e "  4. Session ouverte — dashboard disponible !"
echo ""
