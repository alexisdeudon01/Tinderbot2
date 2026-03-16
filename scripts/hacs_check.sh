#!/usr/bin/env bash
# =============================================================================
# hacs_check.sh — Vérifie que les cartes HACS requises sont installées
# dans Home Assistant et affiche les instructions d'installation si nécessaire.
#
# Usage : bash scripts/hacs_check.sh [HA_CONFIG_DIR]
#   HA_CONFIG_DIR : chemin vers le dossier config HA (défaut: /config)
# =============================================================================

set -euo pipefail

HA_CONFIG="${1:-/config}"
WWW_DIR="${HA_CONFIG}/www"
HACS_DIR="${HA_CONFIG}/.storage"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}=== Tinder MCP — Vérification des cartes HACS ===${NC}"
echo ""

# Liste des ressources requises : "nom_affichage|fichier_js_attendu|repo_github"
REQUIRED_CARDS=(
    "Mushroom Cards|mushroom.js|piitaya/lovelace-mushroom"
    "Button Card|button-card.js|custom-cards/button-card"
    "Mini Graph Card|mini-graph-card-bundle.js|kalkih/mini-graph-card"
)

ALL_OK=true

check_card() {
    local display_name="$1"
    local js_file="$2"
    local github_repo="$3"

    # Check in www/ folder (manual install)
    local found_manual=false
    if [ -f "${WWW_DIR}/${js_file}" ]; then
        found_manual=true
    fi

    # Check in HACS storage (hacs frontend install)
    local found_hacs=false
    if [ -d "${HA_CONFIG}/www/community" ]; then
        if find "${HA_CONFIG}/www/community" -name "${js_file}" 2>/dev/null | grep -q .; then
            found_hacs=true
        fi
    fi

    if $found_manual || $found_hacs; then
        echo -e "  ${GREEN}✓${NC} ${display_name} — installé"
    else
        ALL_OK=false
        echo -e "  ${RED}✗${NC} ${display_name} — ${YELLOW}NON TROUVÉ${NC}"
        echo -e "    → Installe via HACS :"
        echo -e "       HACS > Frontend > Rechercher \"${display_name}\" > Télécharger"
        echo -e "    → Ou repo GitHub : https://github.com/${github_repo}"
        echo ""
    fi
}

for card in "${REQUIRED_CARDS[@]}"; do
    IFS='|' read -r name file repo <<< "$card"
    check_card "$name" "$file" "$repo"
done

echo ""
if $ALL_OK; then
    echo -e "${GREEN}Toutes les cartes requises sont installées.${NC}"
    echo -e "Tu peux importer le dashboard via :"
    echo -e "  Paramètres > Tableaux de bord > Ajouter un tableau de bord (YAML brut)"
    echo -e "  Puis coller le contenu de lovelace/tinder_dashboard.yaml"
else
    echo -e "${RED}Des cartes manquent. Installe-les via HACS puis redémarre HA.${NC}"
    echo ""
    echo -e "${YELLOW}Étapes rapides :${NC}"
    echo -e "  1. Ouvre HA > HACS > Frontend"
    echo -e "  2. Cherche et installe chaque carte manquante"
    echo -e "  3. Vide le cache navigateur (Ctrl+Shift+R)"
    echo -e "  4. Relance ce script pour vérifier"
fi
echo ""
