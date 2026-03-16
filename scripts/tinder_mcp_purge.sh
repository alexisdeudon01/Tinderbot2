#!/usr/bin/env bash
# =============================================================================
# tinder_mcp_purge.sh — Désinstalle / supprime tout ce qu'on a ajouté
# - Supprime l'add-on local tinder_mcp_server (dossier + uninstall si possible)
# - Supprime l'intégration custom_components/tinder_mcp
# - Supprime le dashboard YAML /config/dashboards/tinder_mcp.yaml
# - Retire le bloc "Tinder MCP Dashboard" de /config/configuration.yaml
# - Optionnel: retire le repo add-on du store
#
# À exécuter depuis le Terminal HAOS (core-ssh).
# =============================================================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
step() { echo -e "\n${BLUE}▶ $1${NC}"; }
ok()   { echo -e "  ${GREEN}✓ $1${NC}"; }
warn() { echo -e "  ${YELLOW}⚠ $1${NC}"; }
err()  { echo -e "  ${RED}✗ $1${NC}"; }

ADDON_SLUG="tinder_mcp_server"
ADDON_REPO="https://github.com/alexisdeudon01/Tinderbot2"

CONFIG_DIR="/config"
CC_DIR="$CONFIG_DIR/custom_components/tinder_mcp"
DASH_DIR="$CONFIG_DIR/dashboards"
DASH_FILE="$DASH_DIR/tinder_mcp.yaml"
CONF_YAML="$CONFIG_DIR/configuration.yaml"

LOCAL_ADDON_DIR_1="/addons/local/$ADDON_SLUG"
LOCAL_ADDON_DIR_2="/addons/local/local/$ADDON_SLUG"   # certains systèmes mettent un niveau 'local'

detect_ha_group() {
  # Home Assistant CLI renamed addons -> apps
  if command -v ha >/dev/null 2>&1; then
    if ha apps --help >/dev/null 2>&1; then
      echo "apps"
      return
    fi
    echo "addons"
    return
  fi
  echo ""
}

HA_GROUP="$(detect_ha_group)"

step "1/6 — Arrêt / désinstallation de l'app/add-on (si possible)"
if [ -n "$HA_GROUP" ]; then
  # Stop (ignore errors)
  ha "$HA_GROUP" stop "$ADDON_SLUG" >/dev/null 2>&1 && ok "Arrêt demandé" || warn "Impossible d'arrêter via CLI (peut être non installé)"

  # Uninstall (ignore errors)
  if ha "$HA_GROUP" uninstall "$ADDON_SLUG" >/dev/null 2>&1; then
    ok "Désinstallé via CLI"
  else
    warn "Désinstallation via CLI impossible (normal si local / jamais installé)"
  fi
else
  warn "CLI 'ha' introuvable — skip uninstall"
fi

step "2/6 — Suppression du dossier add-on local"
if [ -d "$LOCAL_ADDON_DIR_1" ]; then
  rm -rf "$LOCAL_ADDON_DIR_1"
  ok "Supprimé: $LOCAL_ADDON_DIR_1"
else
  warn "Absent: $LOCAL_ADDON_DIR_1"
fi
if [ -d "$LOCAL_ADDON_DIR_2" ]; then
  rm -rf "$LOCAL_ADDON_DIR_2"
  ok "Supprimé: $LOCAL_ADDON_DIR_2"
else
  warn "Absent: $LOCAL_ADDON_DIR_2"
fi

step "3/6 — Suppression de l'intégration custom_components"
if [ -d "$CC_DIR" ]; then
  rm -rf "$CC_DIR"
  ok "Supprimé: $CC_DIR"
else
  warn "Absent: $CC_DIR"
fi

step "4/6 — Suppression du dashboard YAML"
if [ -f "$DASH_FILE" ]; then
  rm -f "$DASH_FILE"
  ok "Supprimé: $DASH_FILE"
else
  warn "Absent: $DASH_FILE"
fi

step "5/6 — Retrait du bloc dashboard dans configuration.yaml"
if [ -f "$CONF_YAML" ]; then
  # Retire exactement le bloc que notre install ajoutait:
  #   # Tinder MCP Dashboard
  #   lovelace:
  #     dashboards:
  #       tinder-mcp:
  #         ...
  TMP_FILE="$(mktemp)"
  awk '
    BEGIN { skip=0 }
    /^# Tinder MCP Dashboard$/ { skip=1; next }
    skip==1 {
      # Fin du bloc quand on rencontre une ligne non indentée OU fin de fichier.
      # Le bloc ajouté était en bas de fichier; on coupe aussi les lignes vides immédiatement après.
      if ($0 ~ /^[^[:space:]]/ ) { skip=0 }
      else { next }
    }
    skip==0 { print }
  ' "$CONF_YAML" > "$TMP_FILE"
  mv "$TMP_FILE" "$CONF_YAML"
  ok "Bloc retiré (si présent)"
else
  warn "Absent: $CONF_YAML"
fi

step "6/6 — Retirer le repo add-on du store (optionnel)"
if [ -n "$HA_GROUP" ]; then
  if ha store repositories remove "$ADDON_REPO" >/dev/null 2>&1; then
    ok "Repo retiré du store"
  else
    warn "Repo non retiré (peut déjà être absent)"
  fi
  ha store reload >/dev/null 2>&1 || true
else
  warn "CLI 'ha' introuvable — skip store repo removal"
fi

echo ""
echo -e "${GREEN}Purge terminée.${NC}"
echo -e "${YELLOW}Important:${NC} si tu as ajouté l'intégration \"Tinder MCP\" dans l'UI,"
echo "supprime-la aussi via: Paramètres > Appareils et services > Tinder MCP > Supprimer."
echo ""

