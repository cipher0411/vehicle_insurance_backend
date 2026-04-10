#!/bin/bash

echo "Deploying Vehicle Insurance Backend..."

# Pull latest changes
git pull origin main

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Restart services
sudo systemctl restart gunicorn
sudo systemctl restart nginx
sudo systemctl restart celery
sudo systemctl restart celery-beat

echo "Deployment completed!"