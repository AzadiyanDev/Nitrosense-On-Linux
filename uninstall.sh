#!/usr/bin/env bash
# ==============================================================================
# NitroSense On Linux - Uninstaller
# ==============================================================================

set -e

BOLD="\033[1m"
RESET="\033[0m"
RED="\033[38;5;196m"
GREEN="\033[38;5;46m"
YELLOW="\033[38;5;220m"
CYAN="\033[38;5;51m"

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}[ERROR] This uninstaller must be run as root.${RESET}"
    echo -e "${YELLOW}Please run:${RESET} sudo ./uninstall.sh"
    exit 1
fi

REAL_USER="${SUDO_USER:-$USER}"
USER_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)
EXTENSION_UUID="nitrosense-quicksettings@azadiyan"

echo -e "${CYAN}▶ Stopping and disabling background daemon...${RESET}"
systemctl stop nitrosensed.service 2>/dev/null || true
systemctl disable nitrosensed.service 2>/dev/null || true

echo -e "${CYAN}▶ Removing systemd units & hooks...${RESET}"
rm -f /etc/systemd/system/nitrosensed.service
rm -f /usr/lib/systemd/system-sleep/nitrosense-sleep.sh
rm -f /etc/tmpfiles.d/nitro-platform-profile.conf
systemctl daemon-reload

echo -e "${CYAN}▶ Removing binaries and application files...${RESET}"
rm -f /usr/local/bin/nitrosense
rm -f /usr/local/bin/nitrosensed
rm -rf /usr/local/share/nitrosense
rm -f /usr/local/share/applications/nitrosense.desktop
rm -f /usr/local/share/icons/hicolor/scalable/apps/nitrosense.svg

if command -v update-desktop-database &>/dev/null; then
    update-desktop-database /usr/local/share/applications || true
fi
if command -v gtk-update-icon-cache &>/dev/null; then
    gtk-update-icon-cache -f /usr/local/share/icons/hicolor || true
fi

echo -e "${CYAN}▶ Removing GNOME Shell extension...${RESET}"
rm -rf "/usr/share/gnome-shell/extensions/$EXTENSION_UUID"
if [ -n "$USER_HOME" ]; then
    rm -rf "$USER_HOME/.local/share/gnome-shell/extensions/$EXTENSION_UUID"
    sudo -u "$REAL_USER" python3 -c "
import subprocess, ast
try:
    res = subprocess.run(['gsettings', 'get', 'org.gnome.shell', 'enabled-extensions'], capture_output=True, text=True)
    if res.returncode == 0:
        val = res.stdout.strip()
        arr = ast.literal_eval(val) if val.startswith('[') else []
        if '$EXTENSION_UUID' in arr:
            arr.remove('$EXTENSION_UUID')
            subprocess.run(['gsettings', 'set', 'org.gnome.shell', 'enabled-extensions', str(arr)])
except Exception:
    pass
" 2>/dev/null || true
fi

# Ask or remove config
rm -rf /etc/nitrosense

echo -e "\n${GREEN}${BOLD}✓ NitroSense On Linux has been completely uninstalled.${RESET}\n"
