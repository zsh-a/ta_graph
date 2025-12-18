#!/bin/bash

# Docker Helper Script for ta-graph Trading System
# Provides convenient commands for managing the Docker container

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Check if .env file exists
check_env_file() {
    if [ ! -f .env ]; then
        print_warning ".env file not found!"
        print_info "Creating from .env.example..."
        if [ -f .env.example ]; then
            cp .env.example .env
            print_success ".env file created. Please edit it with your API keys."
            exit 1
        else
            print_error ".env.example not found. Cannot proceed."
            exit 1
        fi
    fi
}

# Main command handling
case "$1" in
    start)
        print_info "Starting trading system..."
        check_env_file
        docker-compose up -d
        print_success "Trading system started"
        print_info "View logs with: $0 logs"
        ;;
    
    stop)
        print_info "Stopping trading system..."
        docker-compose down
        print_success "Trading system stopped"
        ;;
    
    restart)
        print_info "Restarting trading system..."
        docker-compose restart
        print_success "Trading system restarted"
        ;;
    
    logs)
        print_info "Showing logs (Ctrl+C to exit)..."
        docker-compose logs -f --tail=100 trading-system
        ;;
    
    build)
        print_info "Building Docker image..."
        docker-compose build --no-cache
        print_success "Build complete"
        ;;
    
    rebuild)
        print_info "Rebuilding and restarting..."
        docker-compose down
        docker-compose build --no-cache
        docker-compose up -d
        print_success "Rebuild complete"
        ;;
    
    status)
        print_info "Container status:"
        docker-compose ps
        ;;
    
    shell)
        print_info "Opening shell in container..."
        docker-compose exec trading-system /bin/bash
        ;;
    
    clean)
        print_warning "This will remove containers, volumes, and prune system!"
        read -p "Are you sure? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_info "Cleaning up..."
            docker-compose down -v
            docker system prune -f
            print_success "Cleanup complete"
        else
            print_info "Cleanup cancelled"
        fi
        ;;
    
    backup)
        BACKUP_FILE="backup-$(date +%Y%m%d-%H%M%S).tar.gz"
        print_info "Creating backup: $BACKUP_FILE"
        tar czf "$BACKUP_FILE" data/ logs/ charts/ 2>/dev/null || true
        print_success "Backup saved: $BACKUP_FILE"
        ;;
    
    health)
        print_info "Checking container health..."
        docker-compose exec trading-system python -c "
import os
import sqlite3
from datetime import datetime

print('Container Health Check')
print('=' * 50)
print(f'Time: {datetime.now()}')
print(f'Data dir exists: {os.path.exists(\"/app/data\")}')
print(f'Logs dir exists: {os.path.exists(\"/app/logs\")}')

try:
    conn = sqlite3.connect('/app/data/trading_state.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM checkpoints')
    count = cursor.fetchone()[0]
    print(f'Database accessible: Yes ({count} checkpoints)')
    conn.close()
except Exception as e:
    print(f'Database accessible: Error - {e}')

print('=' * 50)
        "
        ;;
    
    *)
        echo "ta-graph Docker Helper"
        echo ""
        echo "Usage: $0 {command}"
        echo ""
        echo "Available commands:"
        echo "  start    - Start the trading system"
        echo "  stop     - Stop the trading system"
        echo "  restart  - Restart the trading system"
        echo "  logs     - View real-time logs"
        echo "  build    - Build Docker image"
        echo "  rebuild  - Rebuild and restart"
        echo "  status   - Show container status"
        echo "  shell    - Open shell in container"
        echo "  clean    - Remove containers and prune system"
        echo "  backup   - Backup data, logs, and charts"
        echo "  health   - Check container health"
        echo ""
        exit 1
        ;;
esac

exit 0
