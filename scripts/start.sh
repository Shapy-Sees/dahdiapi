#!/bin/bash
# scripts/start.sh

# Enable error handling
set -e

# Set up logging
exec 1> >(tee -a /var/log/dahdi_phone/install.log)
exec 2>&1

echo "[$(date)] Starting DAHDI initialization..."

# Verify Python environment
echo "[$(date)] Verifying Python environment..."
python3 -c "import dahdi_phone" || {
    echo "[$(date)] ERROR: dahdi_phone package not found!"
    echo "PYTHONPATH is set to: $PYTHONPATH"
    echo "Installed packages:"
    pip3 list
    exit 1
}

# Load DAHDI modules if we're running with the right capabilities
if [ -w /dev/dahdi_ctl ]; then
    echo "[$(date)] Loading DAHDI kernel modules..."
    modprobe dahdi || true
    modprobe dahdi_dummy || true

    # Generate DAHDI configuration
    echo "[$(date)] Generating DAHDI configuration..."
    dahdi_genconf || true

    # Configure DAHDI
    echo "[$(date)] Configuring DAHDI..."
    dahdi_cfg -vv || true

    # Verify DAHDI status
    echo "[$(date)] Verifying DAHDI status..."
    dahdi_scan || echo "[$(date)] WARNING: DAHDI hardware not detected (may be normal in containerized environment)"
fi

# Create and set permissions for log directories
mkdir -p /var/log/dahdi_build/
mkdir -p /var/log/dahdi_phone/
touch /var/log/dahdi_phone/dahdi_phone.log
chmod -R 777 /var/log/dahdi_phone/
echo "Log directories prepared:"
ls -la /var/log/dahdi_phone/

# Start the API service
echo "[$(date)] Starting DAHDI Phone API service..."

# Verify script permissions
if [[ ! -x "/start.sh" ]]; then
    echo "ERROR: /start.sh is not executable"
    ls -l /start.sh
    exit 1
fi

# Verify config files exist
if [[ ! -f "/etc/dahdi_phone/config.yml" ]]; then
    echo "ERROR: Config file not found at /etc/dahdi_phone/config.yml"
    ls -l /etc/dahdi_phone/
    exit 1
fi

if [[ ! -f "/etc/dahdi_phone/default.yml" ]]; then
    echo "ERROR: Default config file not found at /etc/dahdi_phone/default.yml"
    ls -l /etc/dahdi_phone/
    exit 1
fi

echo "Config files found:"
ls -la /etc/dahdi_phone/

# Start through __main__.py to ensure proper configuration loading
exec python3 -m dahdi_phone.api
