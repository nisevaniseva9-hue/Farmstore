#!/usr/bin/env bash
# Exit on error
set -o errexit

# Install python dependencies
pip install -r requirements.txt

# Create logs directory
mkdir -p logs

# Collect static files for WhiteNoise
python manage.py collectstatic --no-input

