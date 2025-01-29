# scripts/start.sh

#!/bin/bash

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

# Create log directory if it doesn't exist
mkdir -p /var/log/dahdi_build/
echo "DAHDI build logs available in /var/log/dahdi_build/"

# Start the API service
echo "[$(date)] Starting DAHDI Phone API service..."
exec python3 -m dahdi_phone.api.server