#!/bin/bash
set -e

echo "Starting DP Remarks Service..."

# No migrations needed for this service (stateless)
echo "Launching application..."
exec "$@"
