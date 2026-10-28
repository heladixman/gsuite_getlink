#!/bin/bash
# ==============================================================================
# Script Setup Ubuntu 24.04 / 22.04 LTS untuk Bot CapCut / Playwright + GUI RDP
# ==============================================================================
set -e

echo "=== [1/6] Memperbarui Repositori Sistem & Paket ==="
sudo apt update && sudo apt upgrade -y
sudo apt install -y wget curl git software-properties-common apt-transport-https ca-certificates gnupg dbus-x11

echo "=== [2/6] Menginstal Desktop Environment Ringan (XFCE4) & XRDP (Remote Desktop) ==="
sudo DEBIAN_FRONTEND=noninteractive apt install -y xfce4 xfce4-goodies xrdp

# Konfigurasi XRDP agar membuka session XFCE
echo "xfce4-session" > ~/.xsession
sudo adduser xrdp ssl-cert || true

# Cegah popup authentication polkit di Ubuntu XRDP
sudo bash -c 'cat <<EOF > /etc/polkit-1/localauthority/50-local.d/45-allow-colord.pkla
[Allow Colord all Users]
Identity=unix-user:*
Action=org.freedesktop.color-manager.create-device;org.freedesktop.color-manager.create-profile;org.freedesktop.color-manager.delete-device;org.freedesktop.color-manager.delete-profile;org.freedesktop.color-manager.modify-device;org.freedesktop.color-manager.modify-profile
ResultAny=no
ResultInactive=no
ResultActive=yes
EOF' 2>/dev/null || true

sudo systemctl enable xrdp
sudo systemctl restart xrdp

echo "=== [3/6] Menginstal Google Chrome Resmi (Stable) ==="
wget -q -O /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install -y /tmp/google-chrome.deb
rm -f /tmp/google-chrome.deb

echo "=== [4/6] Menginstal Python3, Pip, dan Virtual Environment ==="
sudo apt install -y python3 python3-pip python3-venv python3-full

echo "=== [5/6] Menyiapkan Virtual Environment Python & Install Requirements ==="
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "=== [6/6] Menginstal Dependensi Sistem Playwright ==="
playwright install-deps
playwright install chromium || true

echo "=============================================================================="
echo " [OK] INSTALASI SELESAI!"
echo "=============================================================================="
echo "Cara Remote Desktop (RDP):"
echo "1. Buka 'Remote Desktop Connection' di PC/Laptop Anda."
echo "2. Masukkan IP VPS Anda."
echo "3. Masukkan username (misal: ubuntu atau root) dan password VPS Anda."
echo "4. Anda akan masuk ke tampilan Desktop XFCE dengan Google Chrome terpasang."
echo ""
echo "Cara Menjalankan Bot di Terminal VPS / RDP:"
echo "   cd $(pwd)"
echo "   source venv/bin/activate"
echo "   python3 main.py"
echo "=============================================================================="
