# dahdi-phone-api/scripts/start.sh

#!/bin/bash

# Enable error handling
set -e

# Set up logging
exec 1> >(tee -a /var/log/dahdi_phone/install.log)
exec 2>&1

echo "[$(date)] Starting DAHDI initialization..."

# Load DAHDI modules
echo "[$(date)] Loading DAHDI kernel modules..."
modprobe dahdi
modprobe dahdi_dummy

# Generate DAHDI configuration
echo "[$(date)] Generating DAHDI configuration..."
dahdi_genconf

# Configure DAHDI
echo "[$(date)] Configuring DAHDI..."
dahdi_cfg -vv

# Verify DAHDI status
echo "[$(date)] Verifying DAHDI status..."
dahdi_scan || {
    echo "[$(date)] ERROR: DAHDI initialization failed!"
    exit 1
}

# Start the API service
echo "[$(date)] Starting DAHDI Phone API service..."
python3 -m dahdi_phone.api.server