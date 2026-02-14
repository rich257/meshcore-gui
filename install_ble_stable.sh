#!/usr/bin/env bash
# ============================================================================
# MeshCore GUI — BLE Stabiliteit: Installatiescript
# ============================================================================
#
# Installeert de BLE PIN agent, reconnect module, systemd service
# en D-Bus policy.  Detecteert automatisch de juiste paden en user.
#
# Gebruik:
#   cd ~/meshcore-gui        # (of waar je project ook staat)
#   bash install_ble_stable.sh
#
# Optioneel:
#   bash install_ble_stable.sh --uninstall   # Verwijder alles
#
# Vereisten:
#   - meshcore-gui project met venv/ directory
#   - sudo toegang (voor systemd en D-Bus config)
#
# ============================================================================

set -euo pipefail

# ── Kleuren ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Uninstall mode ──
if [[ "${1:-}" == "--uninstall" ]]; then
    info "Verwijderen van meshcore-gui service en configuratie..."
    sudo systemctl stop meshcore-gui 2>/dev/null || true
    sudo systemctl disable meshcore-gui 2>/dev/null || true
    sudo rm -f /etc/systemd/system/meshcore-gui.service
    sudo rm -f /etc/dbus-1/system.d/meshcore-ble.conf
    sudo systemctl daemon-reload
    sudo systemctl reset-failed 2>/dev/null || true
    ok "Service en configuratie verwijderd"
    info "Python-bestanden in je project zijn NIET verwijderd."
    info "Verwijder handmatig indien gewenst:"
    info "  rm meshcore_gui/ble/ble_agent.py"
    info "  rm meshcore_gui/ble/ble_reconnect.py"
    exit 0
fi

# ── Detecteer omgeving ──
info "Omgeving detecteren..."

# Huidige directory moet het project zijn
if [[ ! -f "meshcore_gui.py" ]] && [[ ! -d "meshcore_gui" ]]; then
    error "Dit script moet worden uitgevoerd vanuit de meshcore-gui project directory.
       Verwacht: meshcore_gui.py of meshcore_gui/ directory.
       Huidige directory: $(pwd)"
fi

PROJECT_DIR="$(pwd)"
CURRENT_USER="$(whoami)"
VENV_PYTHON="${PROJECT_DIR}/venv/bin/python"

# Check venv
if [[ ! -x "${VENV_PYTHON}" ]]; then
    error "Virtual environment niet gevonden op: ${VENV_PYTHON}
       Maak deze eerst aan:
         python3 -m venv venv
         source venv/bin/activate
         pip install meshcore nicegui"
fi

# Bepaal het entry point
if [[ -f "${PROJECT_DIR}/meshcore_gui.py" ]]; then
    ENTRY_POINT="meshcore_gui.py"
elif [[ -d "${PROJECT_DIR}/meshcore_gui" ]]; then
    ENTRY_POINT="-m meshcore_gui"
else
    error "Kan entry point niet bepalen."
fi

# Check BLE adres argument
BLE_ADDRESS="${BLE_ADDRESS:-}"
if [[ -z "${BLE_ADDRESS}" ]]; then
    echo ""
    echo -e "${YELLOW}BLE MAC-adres is niet opgegeven.${NC}"
    echo "Je kunt het op twee manieren opgeven:"
    echo ""
    echo "  1. Als environment variable:"
    echo "     BLE_ADDRESS=FF:05:D6:71:83:8D bash install_ble_stable.sh"
    echo ""
    echo "  2. Handmatig invoeren:"
    read -rp "     BLE MAC-adres (bijv. FF:05:D6:71:83:8D): " BLE_ADDRESS
    echo ""
fi

if [[ -z "${BLE_ADDRESS}" ]]; then
    error "Geen BLE MAC-adres opgegeven. Afgebroken."
fi

# Samenvatting
echo ""
echo "═══════════════════════════════════════════════════"
echo " MeshCore GUI — BLE Stabiliteit Installer"
echo "═══════════════════════════════════════════════════"
echo " Project dir:  ${PROJECT_DIR}"
echo " User:         ${CURRENT_USER}"
echo " Python:       ${VENV_PYTHON}"
echo " Entry point:  ${ENTRY_POINT}"
echo " BLE adres:    ${BLE_ADDRESS}"
echo "═══════════════════════════════════════════════════"
echo ""
read -rp "Doorgaan? [j/N] " confirm
if [[ "${confirm}" != "j" && "${confirm}" != "J" && "${confirm}" != "y" && "${confirm}" != "Y" ]]; then
    info "Afgebroken."
    exit 0
fi

# ── Stap 1: Upgrade meshcore library ──
info "Stap 1/6: meshcore library upgraden..."
"${PROJECT_DIR}/venv/bin/pip" install --upgrade meshcore --quiet 2>/dev/null || \
    "${PROJECT_DIR}/venv/bin/pip" install --upgrade meshcore
MESHCORE_VERSION=$("${PROJECT_DIR}/venv/bin/pip" show meshcore 2>/dev/null | grep "^Version:" | awk '{print $2}')
ok "meshcore versie: ${MESHCORE_VERSION:-onbekend}"

# ── Stap 2: Check dat dbus_fast beschikbaar is ──
info "Stap 2/6: dbus_fast dependency checken..."
if "${VENV_PYTHON}" -c "import dbus_fast" 2>/dev/null; then
    ok "dbus_fast beschikbaar (meegeleverd met bleak)"
else
    warn "dbus_fast niet gevonden, installeren..."
    "${PROJECT_DIR}/venv/bin/pip" install dbus-fast --quiet
    ok "dbus_fast geïnstalleerd"
fi

# ── Stap 3: Python bestanden kopiëren ──
info "Stap 3/6: Python bestanden installeren..."

# Detecteer of ble_agent.py en ble_reconnect.py al bestaan
BLE_DIR="${PROJECT_DIR}/meshcore_gui/ble"
if [[ ! -d "${BLE_DIR}" ]]; then
    error "Directory ${BLE_DIR} niet gevonden."
fi

# Check of de bestanden al op hun plek staan
AGENT_OK=false
RECONNECT_OK=false
[[ -f "${BLE_DIR}/ble_agent.py" ]] && AGENT_OK=true
[[ -f "${BLE_DIR}/ble_reconnect.py" ]] && RECONNECT_OK=true

if $AGENT_OK && $RECONNECT_OK; then
    ok "ble_agent.py en ble_reconnect.py zijn al geïnstalleerd"
else
    # Check of ze in dezelfde directory als dit script staan
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    
    if [[ -f "${SCRIPT_DIR}/meshcore_gui/ble/ble_agent.py" ]]; then
        cp "${SCRIPT_DIR}/meshcore_gui/ble/ble_agent.py" "${BLE_DIR}/"
        cp "${SCRIPT_DIR}/meshcore_gui/ble/ble_reconnect.py" "${BLE_DIR}/"
        ok "Bestanden gekopieerd vanuit ${SCRIPT_DIR}"
    else
        if ! $AGENT_OK; then
            error "ble_agent.py niet gevonden in ${BLE_DIR}/
       Kopieer dit bestand eerst handmatig naar ${BLE_DIR}/"
        fi
        if ! $RECONNECT_OK; then
            error "ble_reconnect.py niet gevonden in ${BLE_DIR}/
       Kopieer dit bestand eerst handmatig naar ${BLE_DIR}/"
        fi
    fi
fi

# Verify Python syntax
info "Python syntax verifiëren..."
"${VENV_PYTHON}" -c "
import ast, sys
errors = []
for f in ['${BLE_DIR}/ble_agent.py', '${BLE_DIR}/ble_reconnect.py', '${BLE_DIR}/worker.py']:
    try:
        ast.parse(open(f).read())
    except SyntaxError as e:
        errors.append(f'{f}: {e}')
if errors:
    print('SYNTAX ERRORS:')
    for e in errors:
        print(f'  {e}')
    sys.exit(1)
print('OK')
" || error "Syntax errors gevonden in Python bestanden"
ok "Alle Python bestanden zijn syntactisch correct"

# ── Stap 4: Oude bt-agent service verwijderen ──
info "Stap 4/6: Oude services opruimen..."
if systemctl is-active --quiet bt-agent 2>/dev/null; then
    sudo systemctl stop bt-agent
    sudo systemctl disable bt-agent
    ok "bt-agent.service gestopt en uitgeschakeld"
elif systemctl list-unit-files | grep -q bt-agent 2>/dev/null; then
    sudo systemctl disable bt-agent 2>/dev/null || true
    ok "bt-agent.service uitgeschakeld"
else
    ok "bt-agent.service was al afwezig"
fi

# Stop bestaande meshcore-gui service als die draait
if systemctl is-active --quiet meshcore-gui 2>/dev/null; then
    sudo systemctl stop meshcore-gui
    ok "Bestaande meshcore-gui.service gestopt"
fi

# ── Stap 5: D-Bus policy installeren ──
info "Stap 5/6: D-Bus policy installeren..."
DBUS_CONF="/etc/dbus-1/system.d/meshcore-ble.conf"

sudo tee "${DBUS_CONF}" > /dev/null << DBUS_EOF
<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-BUS Bus Configuration 1.0//EN"
  "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <!-- Allow user '${CURRENT_USER}' to interact with BlueZ for BLE pairing agent -->
  <policy user="${CURRENT_USER}">
    <allow send_destination="org.bluez"/>
    <allow send_interface="org.bluez.Agent1"/>
    <allow send_interface="org.bluez.AgentManager1"/>
  </policy>
</busconfig>
DBUS_EOF

ok "D-Bus policy geïnstalleerd voor user '${CURRENT_USER}'"

# ── Stap 6: Systemd service installeren ──
info "Stap 6/6: Systemd service installeren..."
SERVICE_FILE="/etc/systemd/system/meshcore-gui.service"

sudo tee "${SERVICE_FILE}" > /dev/null << SERVICE_EOF
[Unit]
Description=MeshCore GUI (BLE)
After=bluetooth.target
Wants=bluetooth.target

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${PROJECT_DIR}
ExecStart=${VENV_PYTHON} ${ENTRY_POINT} ${BLE_ADDRESS} --debug-on
Restart=on-failure
RestartSec=30
Environment=DBUS_SYSTEM_BUS_ADDRESS=unix:path=/var/run/dbus/system_bus_socket

[Install]
WantedBy=multi-user.target
SERVICE_EOF

sudo systemctl daemon-reload
sudo systemctl enable meshcore-gui
ok "meshcore-gui.service geïnstalleerd en geactiveerd"

# ── Klaar ──
echo ""
echo "═══════════════════════════════════════════════════"
echo -e " ${GREEN}Installatie voltooid!${NC}"
echo "═══════════════════════════════════════════════════"
echo ""
echo " Commando's:"
echo "   sudo systemctl start meshcore-gui      # Starten"
echo "   sudo systemctl stop meshcore-gui       # Stoppen"
echo "   sudo systemctl restart meshcore-gui    # Herstarten"
echo "   sudo systemctl status meshcore-gui     # Status"
echo "   journalctl -u meshcore-gui -f          # Live logs"
echo ""
echo " Verwijderen:"
echo "   bash install_ble_stable.sh --uninstall"
echo ""
echo "═══════════════════════════════════════════════════"

# Optioneel direct starten
echo ""
read -rp "Service nu starten? [j/N] " start_now
if [[ "${start_now}" == "j" || "${start_now}" == "J" || "${start_now}" == "y" || "${start_now}" == "Y" ]]; then
    sudo systemctl start meshcore-gui
    sleep 2
    if systemctl is-active --quiet meshcore-gui; then
        ok "Service draait!"
        echo ""
        info "Live logs bekijken: journalctl -u meshcore-gui -f"
    else
        warn "Service kon niet starten. Check logs:"
        echo "  journalctl -u meshcore-gui --no-pager -n 20"
    fi
fi
