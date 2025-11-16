#!/bin/bash

# RMCitecraft E2E Test Runner
# This script helps run end-to-end tests with proper Chrome setup

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print header
echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  RMCitecraft E2E Test Runner${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# Check if Chrome is running with remote debugging
echo -e "${YELLOW}Checking Chrome remote debugging status...${NC}"
if ps aux | grep -i chrome | grep -q "\--remote-debugging-port=9222"; then
    echo -e "${GREEN}✓ Chrome is running with remote debugging on port 9222${NC}"
else
    echo -e "${RED}✗ Chrome is NOT running with remote debugging${NC}"
    echo ""
    echo "To launch Chrome with debugging, run:"
    echo ""
    echo -e "${YELLOW}/Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome \\${NC}"
    echo -e "${YELLOW}    --remote-debugging-port=9222 \\${NC}"
    echo -e "${YELLOW}    --user-data-dir=\"\$HOME/Library/Application Support/Google/Chrome-RMCitecraft\"${NC}"
    echo ""
    read -p "Do you want me to launch Chrome now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Launching Chrome with remote debugging...${NC}"
        /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
            --remote-debugging-port=9222 \
            --user-data-dir="$HOME/Library/Application Support/Google/Chrome-RMCitecraft" &
        sleep 3
        echo -e "${GREEN}✓ Chrome launched${NC}"
        echo ""
        echo -e "${YELLOW}Please log into FamilySearch manually in the Chrome window${NC}"
        echo -e "${YELLOW}Press Enter when ready to continue...${NC}"
        read
    else
        echo -e "${RED}Exiting. Please launch Chrome manually and run again.${NC}"
        exit 1
    fi
fi

echo ""

# Parse command line arguments
TEST_PATH="tests/e2e/"
VERBOSE="-v"
EXTRA_ARGS=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --connection)
            TEST_PATH="tests/e2e/test_chrome_connection.py"
            shift
            ;;
        --extraction)
            TEST_PATH="tests/e2e/test_citation_extraction.py"
            shift
            ;;
        --download)
            TEST_PATH="tests/e2e/test_image_download.py"
            shift
            ;;
        --workflow)
            TEST_PATH="tests/e2e/test_complete_workflow.py"
            shift
            ;;
        --all)
            TEST_PATH="tests/e2e/"
            shift
            ;;
        -vv)
            VERBOSE="-vv -s"
            shift
            ;;
        --coverage)
            EXTRA_ARGS="--cov=src/rmcitecraft/services/familysearch_automation --cov-report=html"
            shift
            ;;
        *)
            EXTRA_ARGS="$EXTRA_ARGS $1"
            shift
            ;;
    esac
done

# Show what we're running
echo -e "${BLUE}Running E2E tests:${NC} $TEST_PATH"
echo ""

# Run tests
echo -e "${YELLOW}Starting tests...${NC}"
echo ""

uv run pytest $TEST_PATH $VERBOSE $EXTRA_ARGS

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}================================================${NC}"
    echo -e "${GREEN}  ✓ All tests passed!${NC}"
    echo -e "${GREEN}================================================${NC}"

    if [[ $EXTRA_ARGS == *"--cov"* ]]; then
        echo ""
        echo -e "${YELLOW}Coverage report generated: htmlcov/index.html${NC}"
        echo -e "${YELLOW}Run: open htmlcov/index.html${NC}"
    fi
else
    echo ""
    echo -e "${RED}================================================${NC}"
    echo -e "${RED}  ✗ Some tests failed${NC}"
    echo -e "${RED}================================================${NC}"
    exit 1
fi
