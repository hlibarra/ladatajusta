#!/bin/bash
# Script to run scrapers - designed to be called by cron

cd /home/deploy/apps/ladatajusta

# Log file with date
LOG_FILE="/var/log/ladatajusta/scraper-$(date +%Y%m%d).log"
mkdir -p /var/log/ladatajusta

echo "=== Scraping started at $(date) ===" >> $LOG_FILE

# Run the scraper inside the backend container
docker compose -f docker-compose.prod.yml exec -T backend python -m app.scraping.run_all 2>&1 >> $LOG_FILE

echo "=== Scraping finished at $(date) ===" >> $LOG_FILE

# Clean old logs (keep last 7 days)
find /var/log/ladatajusta -name "scraper-*.log" -mtime +7 -delete
