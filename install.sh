#!/usr/bin/env bash
# ==============================================================================
# NitroSense On Linux - Universal Installer
# Acer Nitro V 15 & Predator Fan, Thermal & Power Controller with GNOME Integration
# ==============================================================================

set -e

# Terminal colors
BOLD="\033[1m"
RESET="\033[0m"
RED="\033[38;5;196m"
GREEN="\033[38;5;46m"
YELLOW="\033[38;5;220m"
CYAN="\033[38;5;51m"
BLUE="\033[38;5;39m"

echo -e "${RED}${BOLD}"
cat << "EOF"
  _   _ _ _             ____                      
 | \ | (_) |_ _ __ ___ / ___|  ___ _ __  ___  ___ 
 |  \| | | __| '__/ _ \\___ \ / _ \ '_ \/ __|/ _ \
 | |\  | | |_| | | (_) |___) |  __/ | | \__ \  __/
 |_| \_|_|\__|_|  \___/|____/ \___|_| |_|___/\___|
             Acer Nitro & Predator Linux Edition
EOF
echo -e "${RESET}"

# 1. Check Root Privileges
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}[ERROR] This installer must be run as root.${RESET}"
    echo -e "${YELLOW}Please run:${RESET} sudo ./install.sh"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REAL_USER="${SUDO_USER:-$USER}"
USER_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)

echo -e "${CYAN}▶ Detecting system distribution and package manager...${RESET}"

# 2. Install Dependencies based on Distribution
if command -v dnf &>/dev/null; then
    echo -e "${GREEN}✓ Detected Fedora / RHEL family (dnf)${RESET}"
    echo -e "${CYAN}Installing required packages...${RESET}"
    dnf install -y python3 python3-gobject gtk4 libadwaita tuned git unzip || true

    # TuneD profile compatibility fix
    TUNED_TP="/usr/lib/tuned/profiles/throughput-performance/tuned.conf"
    if [ -f "$TUNED_TP" ]; then
        if grep -q "platform_profile=performance" "$TUNED_TP"; then
            echo -e "${CYAN}Applying Acer platform_profile fix to TuneD throughput-performance...${RESET}"
            sed -i 's/platform_profile=performance/platform_profile=balanced-performance|performance/' "$TUNED_TP"
            systemctl restart tuned 2>/dev/null || true
        fi
    fi

elif command -v apt-get &>/dev/null; then
    echo -e "${GREEN}✓ Detected Debian / Ubuntu family (apt)${RESET}"
    echo -e "${CYAN}Installing required packages...${RESET}"
    apt-get update -y
    apt-get install -y python3 python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 libglib2.0-bin policykit-1 unzip || true

elif command -v pacman &>/dev/null; then
    echo -e "${GREEN}✓ Detected Arch Linux family (pacman)${RESET}"
    echo -e "${CYAN}Installing required packages...${RESET}"
    pacman -Sy --noconfirm python python-gobject gtk4 libadwaita unzip || true

elif command -v zypper &>/dev/null; then
    echo -e "${GREEN}✓ Detected openSUSE family (zypper)${RESET}"
    echo -e "${CYAN}Installing required packages...${RESET}"
    zypper install -y python3 python3-gobject typelib-Gtk-4_0 typelib-Adw-1 unzip || true
else
    echo -e "${YELLOW}[WARNING] Unknown package manager. Please ensure Python3, PyGObject, GTK4 and Libadwaita are installed.${RESET}"
fi

# 3. Kernel module check (acer-wmi)
echo -e "${CYAN}▶ Checking Acer WMI hardware support...${RESET}"
if ! lsmod | grep -q "acer_wmi"; then
    echo -e "${YELLOW}Loading acer-wmi kernel module...${RESET}"
    modprobe acer-wmi || true
fi

# 4. Copy Binaries & Source
echo -e "${CYAN}▶ Installing NitroSense core files...${RESET}"
mkdir -p /usr/local/bin
mkdir -p /usr/local/share/nitrosense
mkdir -p /etc/nitrosense

cp "$SCRIPT_DIR/bin/nitrosense" /usr/local/bin/nitrosense
cp "$SCRIPT_DIR/bin/nitrosensed" /usr/local/bin/nitrosensed
chmod 755 /usr/local/bin/nitrosense /usr/local/bin/nitrosensed

cp "$SCRIPT_DIR/src/backend.py" /usr/local/share/nitrosense/backend.py
cp "$SCRIPT_DIR/src/gui.py" /usr/local/share/nitrosense/gui.py
chmod 755 /usr/local/share/nitrosense/gui.py
chmod 644 /usr/local/share/nitrosense/backend.py

# Initialize config file if not present
if [ ! -f /etc/nitrosense/config.json ]; then
    cat << 'EOF' > /etc/nitrosense/config.json
{
  "profile": "performance",
  "fan_mode": "auto",
  "fan_speed": 60
}
EOF
fi
chmod 777 /etc/nitrosense
chmod 666 /etc/nitrosense/config.json

# 5. Desktop Application Shortcut & Icon
echo -e "${CYAN}▶ Installing desktop shortcut and icons...${RESET}"
mkdir -p /usr/local/share/applications
mkdir -p /usr/local/share/icons/hicolor/scalable/apps

cp "$SCRIPT_DIR/desktop/nitrosense.desktop" /usr/local/share/applications/nitrosense.desktop
cp "$SCRIPT_DIR/desktop/nitrosense.svg" /usr/local/share/icons/hicolor/scalable/apps/nitrosense.svg
chmod 644 /usr/local/share/applications/nitrosense.desktop
chmod 644 /usr/local/share/icons/hicolor/scalable/apps/nitrosense.svg

if command -v update-desktop-database &>/dev/null; then
    update-desktop-database /usr/local/share/applications || true
fi
if command -v gtk-update-icon-cache &>/dev/null; then
    gtk-update-icon-cache -f /usr/local/share/icons/hicolor || true
fi

# 6. Systemd Background Daemon & Sleep Hook
echo -e "${CYAN}▶ Setting up systemd persistence service and sleep hook...${RESET}"
mkdir -p /usr/lib/systemd/system-sleep
mkdir -p /etc/tmpfiles.d

cp "$SCRIPT_DIR/systemd/nitrosensed.service" /etc/systemd/system/nitrosensed.service
cp "$SCRIPT_DIR/systemd/nitrosense-sleep.sh" /usr/lib/systemd/system-sleep/nitrosense-sleep.sh
chmod 755 /usr/lib/systemd/system-sleep/nitrosense-sleep.sh
cp "$SCRIPT_DIR/systemd/nitro-platform-profile.conf" /etc/tmpfiles.d/nitro-platform-profile.conf

systemd-tmpfiles --create /etc/tmpfiles.d/nitro-platform-profile.conf 2>/dev/null || true
systemctl daemon-reload
systemctl enable --now nitrosensed.service

# 7. GNOME Shell Extension Installation
EXTENSION_UUID="nitrosense-quicksettings@azadiyan"
echo -e "${CYAN}▶ Installing GNOME Shell Quick Settings Extension...${RESET}"

# Install System-wide (Available for all users)
SYSTEM_EXT_DIR="/usr/share/gnome-shell/extensions/$EXTENSION_UUID"
mkdir -p "$SYSTEM_EXT_DIR"
cp -r "$SCRIPT_DIR/extension/$EXTENSION_UUID/"* "$SYSTEM_EXT_DIR/"
chmod -R 755 "$SYSTEM_EXT_DIR"

# Install in user's directory if invoked with sudo
if [ -n "$USER_HOME" ] && [ -d "$USER_HOME" ]; then
    USER_EXT_DIR="$USER_HOME/.local/share/gnome-shell/extensions/$EXTENSION_UUID"
    mkdir -p "$USER_EXT_DIR"
    cp -r "$SCRIPT_DIR/extension/$EXTENSION_UUID/"* "$USER_EXT_DIR/"
    chown -R "$REAL_USER:$REAL_USER" "$USER_HOME/.local/share/gnome-shell/extensions"

    # Enable extension in gsettings for the user
    sudo -u "$REAL_USER" python3 -c "
import subprocess, ast
try:
    res = subprocess.run(['gsettings', 'get', 'org.gnome.shell', 'enabled-extensions'], capture_output=True, text=True)
    if res.returncode == 0:
        val = res.stdout.strip()
        arr = ast.literal_eval(val) if val.startswith('[') else []
        if '$EXTENSION_UUID' not in arr:
            arr.append('$EXTENSION_UUID')
            subprocess.run(['gsettings', 'set', 'org.gnome.shell', 'enabled-extensions', str(arr)])
            print('✓ Extension enabled in GNOME Shell configuration.')
except Exception as e:
    pass
" 2>/dev/null || true
fi

echo -e "\n${GREEN}${BOLD}══════════════════════════════════════════════════════════════════${RESET}"
echo -e "${GREEN}${BOLD}   ✓ NitroSense On Linux Successfully Installed!${RESET}"
echo -e "${GREEN}${BOLD}══════════════════════════════════════════════════════════════════${RESET}"
echo -e "${CYAN}Features installed:${RESET}"
echo -e "  • ${BOLD}CLI Tool:${RESET} Run ${YELLOW}nitrosense${RESET} or ${YELLOW}nitrosense watch${RESET}"
echo -e "  • ${BOLD}GUI App:${RESET} Search for 'NitroSense' in your apps menu or run ${YELLOW}nitrosense gui${RESET}"
echo -e "  • ${BOLD}Persistent Service:${RESET} nitrosensed.service is active & running"
echo -e "  • ${BOLD}GNOME Extension:${RESET} Quick Settings toggle & top-bar indicator"
echo -e ""
echo -e "${YELLOW}${BOLD}[IMPORTANT NOTE FOR GNOME WAYLAND USERS]:${RESET}"
echo -e "${YELLOW}To load the new Quick Settings extension into your top bar for the first time,${RESET}"
echo -e "${YELLOW}please ${BOLD}Log Out and Log back In${RESET}${YELLOW} (or restart your PC).${RESET}"
echo -e "${GREEN}After that, NitroSense will be permanently available in your top menu!${RESET}\n"
