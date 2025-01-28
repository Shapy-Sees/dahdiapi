# dahdi-phone-api/Dockerfile

# Use Ubuntu as base image for better package compatibility
FROM ubuntu:22.04

# Add labels for maintainability
LABEL maintainer="DAHDI Phone API Team"
LABEL description="DAHDI Phone API service with WebSocket support"

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies and build tools
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3.10-dev \
    python3-pip \
    wget \
    git \
    build-essential \
    gcc \
    make \
    curl \
    autoconf \
    automake \
    libtool \
    autoconf-archive \
    pkg-config \
    m4 \
    perl \
    libncurses5-dev \
    file \
    linux-headers-generic \
    libusb-1.0-0-dev \
    python3-setuptools \
    && rm -rf /var/lib/apt/lists/*

# Create a build script for DAHDI
RUN echo '#!/bin/bash\n\
set -x\n\
\n\
# Create log directory\n\
mkdir -p /var/log/dahdi_build\n\
\n\
# Download and build DAHDI Linux first\n\
cd /tmp\n\
wget -O dahdi-linux.tar.gz http://downloads.asterisk.org/pub/telephony/dahdi-linux/dahdi-linux-current.tar.gz\n\
tar xvfz dahdi-linux.tar.gz\n\
cd dahdi-linux-*\n\
make 2>&1 | tee /var/log/dahdi_build/dahdi-linux-make.log\n\
make install 2>&1 | tee /var/log/dahdi_build/dahdi-linux-install.log\n\
\n\
# Now build DAHDI tools\n\
cd /tmp\n\
wget -O dahdi-tools.tar.gz http://downloads.asterisk.org/pub/telephony/dahdi-tools/dahdi-tools-current.tar.gz\n\
tar xvfz dahdi-tools.tar.gz\n\
cd dahdi-tools-*\n\
\n\
# Run each step separately with error checking\n\
libtoolize --force --copy --automake 2>&1 | tee /var/log/dahdi_build/libtoolize.log || exit 1\n\
\n\
aclocal 2>&1 | tee /var/log/dahdi_build/aclocal.log || exit 1\n\
\n\
autoheader 2>&1 | tee /var/log/dahdi_build/autoheader.log || exit 1\n\
\n\
automake --add-missing --copy --force-missing 2>&1 | tee /var/log/dahdi_build/automake.log || exit 1\n\
\n\
autoconf 2>&1 | tee /var/log/dahdi_build/autoconf.log || exit 1\n\
\n\
# Add m4 pattern allows\n\
echo "m4_pattern_allow([^AC_.*])" >> aclocal.m4\n\
echo "m4_pattern_allow([^AM_.*])" >> aclocal.m4\n\
\n\
./configure --enable-debug 2>&1 | tee /var/log/dahdi_build/configure.log || exit 1\n\
\n\
make 2>&1 | tee /var/log/dahdi_build/make.log || exit 1\n\
\n\
make install 2>&1 | tee /var/log/dahdi_build/make_install.log || exit 1\n\
\n\
# Update library cache\n\
ldconfig\n\
\n\
# Build and install python-dahdi from source\n\
cd /tmp\n\
git clone https://github.com/asterisk/python-dahdi.git\n\
cd python-dahdi\n\
python3 setup.py build 2>&1 | tee /var/log/dahdi_build/python-dahdi-build.log || exit 1\n\
python3 setup.py install 2>&1 | tee /var/log/dahdi_build/python-dahdi-install.log || exit 1\n\
\n\
# Cleanup\n\
cd /\n\
rm -rf /tmp/dahdi-* /tmp/python-dahdi\n\
' > /usr/local/bin/build-dahdi.sh && chmod +x /usr/local/bin/build-dahdi.sh

# Run the DAHDI build script
RUN /usr/local/bin/build-dahdi.sh || { \
    echo "Build failed. Dumping all logs:"; \
    for log in /var/log/dahdi_build/*.log; do \
        echo "=== Contents of $log ==="; \
        cat "$log"; \
    done; \
    exit 1; \
}

# Set working directory
WORKDIR /app

# Copy requirements first for better cache utilization
COPY requirements.txt .

# Install Python dependencies with verbose output for debugging
RUN pip3 install --no-cache-dir -v -r requirements.txt

# Copy project files
COPY . .

# Create necessary directories with proper permissions
RUN mkdir -p /var/log/dahdi_phone && \
    touch /var/log/dahdi_phone/api.log && \
    chmod 777 /var/log/dahdi_phone

# Create configuration directory and copy default config
RUN mkdir -p /etc/dahdi_phone
COPY config/default.yml /etc/dahdi_phone/config.yml

# Expose ports for API and WebSocket
EXPOSE 8000 8001

# Set environment variables
ENV PYTHONPATH=/app \
    LOG_LEVEL=INFO \
    CONFIG_PATH=/etc/dahdi_phone/config.yml \
    DAHDI_LOG_LEVEL=DEBUG \
    PYTHONWARNINGS=default \
    AUTOCONF_DEBUG=1 \
    AUTOMAKE_DEBUG=1

# Health check to verify service is running
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/status || exit 1

# Create entrypoint script with enhanced debugging
RUN echo '#!/bin/bash\n\
set -x\n\
echo "DAHDI build logs available in /var/log/dahdi_build/"\n\
exec python3 -m dahdi_phone.api.server "$@"' > /entrypoint.sh && \
    chmod +x /entrypoint.sh

# Run the API service with detailed logging
ENTRYPOINT ["/entrypoint.sh"]