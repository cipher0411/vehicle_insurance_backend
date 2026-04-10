#!/bin/bash

BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="vehicle_insurance"
DB_USER="postgres"
DB_PASSWORD="password"

mkdir -p $BACKUP_DIR

PGPASSWORD=$DB_PASSWORD pg_dump -h localhost -U $DB_USER $DB_NAME > "$BACKUP_DIR/backup_$DATE.sql"

# Compress backup
gzip "$BACKUP_DIR/backup_$DATE.sql"

# Delete backups older than 30 days
find $BACKUP_DIR -type f -mtime +30 -delete

echo "Database backup completed: backup_$DATE.sql.gz"