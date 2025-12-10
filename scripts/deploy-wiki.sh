#!/bin/bash
#
# Deploy Wiki Pages to GitHub
#
# This script pushes the wiki/ folder contents to the GitHub wiki repository.
#
# Prerequisites:
#   1. Create the first wiki page manually on GitHub (Settings > Wiki > Create first page)
#   2. Have push access to the wiki repository
#
# Usage:
#   ./scripts/deploy-wiki.sh
#   ./scripts/deploy-wiki.sh --remote git@github.com:Shakedp/lock-service.wiki.git
#

set -e

# Configuration
WIKI_DIR="wiki"
TEMP_DIR="/tmp/lock-service-wiki-$$"
DEFAULT_REMOTE="https://github.com/Shakedp/lock-service.wiki.git"

# Parse arguments
REMOTE="${1:-$DEFAULT_REMOTE}"
if [ "$1" == "--remote" ]; then
    REMOTE="$2"
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Lock-Down Service Wiki Deployment${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if wiki directory exists
if [ ! -d "$WIKI_DIR" ]; then
    echo -e "${RED}Error: Wiki directory not found at $WIKI_DIR${NC}"
    exit 1
fi

# Count wiki pages
PAGE_COUNT=$(ls -1 "$WIKI_DIR"/*.md 2>/dev/null | wc -l)
echo -e "Found ${YELLOW}$PAGE_COUNT${NC} wiki pages to deploy"
echo ""

# List pages
echo "Pages to deploy:"
for page in "$WIKI_DIR"/*.md; do
    basename "$page"
done
echo ""

# Confirm deployment
read -p "Deploy to $REMOTE? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled."
    exit 0
fi

echo ""
echo -e "${YELLOW}Cloning wiki repository...${NC}"

# Clean up temp directory if exists
rm -rf "$TEMP_DIR"

# Clone wiki repository
if ! git clone "$REMOTE" "$TEMP_DIR" 2>/dev/null; then
    echo -e "${RED}Error: Failed to clone wiki repository.${NC}"
    echo ""
    echo "Make sure you have:"
    echo "  1. Created the first wiki page on GitHub (go to Wiki tab and create Home page)"
    echo "  2. Have push access to the repository"
    echo ""
    exit 1
fi

echo -e "${YELLOW}Copying wiki pages...${NC}"

# Copy wiki pages to cloned repository
cp "$WIKI_DIR"/*.md "$TEMP_DIR/"

# Change to temp directory
cd "$TEMP_DIR"

# Configure git
git config user.email "wiki-deploy@lock-service"
git config user.name "Wiki Deploy Script"

# Add all changes
git add -A

# Check if there are changes to commit
if git diff --staged --quiet; then
    echo -e "${YELLOW}No changes to deploy. Wiki is up to date.${NC}"
    rm -rf "$TEMP_DIR"
    exit 0
fi

# Show changes
echo ""
echo "Changes to be deployed:"
git diff --staged --stat
echo ""

# Commit changes
git commit -m "Update wiki pages - $(date '+%Y-%m-%d %H:%M:%S')"

# Push to remote
echo -e "${YELLOW}Pushing to GitHub...${NC}"
git push origin master 2>/dev/null || git push origin main

# Cleanup
cd -
rm -rf "$TEMP_DIR"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Wiki deployed successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "View your wiki at:"
echo "  https://github.com/Shakedp/lock-service/wiki"
echo ""
