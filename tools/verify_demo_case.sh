#!/bin/bash
# verify_demo_case.sh - Verify the two-phase solver works on the demo dataset
# 
# This script tests the primary acceptance criterion: a 6-class, 35-teacher
# school must ALWAYS produce a valid timetable.
#
# Usage:
#   ./tools/verify_demo_case.sh [options]
#
# Options:
#   --time-limit SECONDS   Override default time limit (default: 120)
#   --force-fresh          Force a fresh solve, ignore cache
#   --verbose              Show detailed solver output
#   --help                 Show this help message

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default settings
TIME_LIMIT=120
FORCE_FRESH=true
VERBOSE=false
SERVER_URL="${SERVER_URL:-http://localhost:8000}"
API_PREFIX="/api/v1/timetable"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --time-limit)
            TIME_LIMIT="$2"
            shift 2
            ;;
        --force-fresh)
            FORCE_FRESH=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --help)
            head -20 "$0" | tail -15
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Two-Phase Solver Verification Test   ${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Server: $SERVER_URL"
echo "Time limit: ${TIME_LIMIT}s"
echo "Force fresh: $FORCE_FRESH"
echo ""

# Check if server is running
echo -e "${YELLOW}[1/5] Checking server status...${NC}"
if ! curl -s "$SERVER_URL/health" > /dev/null 2>&1; then
    echo -e "${RED}ERROR: Server not responding at $SERVER_URL${NC}"
    echo "Start the server with: cd server && uvicorn app.main:app --reload"
    exit 1
fi
echo -e "${GREEN}✓ Server is running${NC}"

# Submit solve request with sample data
echo ""
echo -e "${YELLOW}[2/5] Submitting demo solve request...${NC}"
echo "Using sample data: sample-data-vidya-mandir (6 classes, 35 teachers)"

SOLVE_RESPONSE=$(curl -s -X POST "$SERVER_URL$API_PREFIX/solve" \
    -H "Content-Type: application/json" \
    -d "{
        \"upload_id\": \"sample-data-vidya-mandir\",
        \"options\": {
            \"time_limit_seconds\": $TIME_LIMIT,
            \"force_fresh\": $FORCE_FRESH,
            \"strategy\": \"balanced\"
        }
    }")

JOB_ID=$(echo "$SOLVE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('job_id', ''))" 2>/dev/null || echo "")

if [ -z "$JOB_ID" ]; then
    echo -e "${RED}ERROR: Failed to create solve job${NC}"
    echo "Response: $SOLVE_RESPONSE"
    exit 1
fi

echo -e "${GREEN}✓ Job created: $JOB_ID${NC}"
echo "Time allocated: $(echo "$SOLVE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('time_allocated_seconds', 'unknown'))")s"

# Poll for completion
echo ""
echo -e "${YELLOW}[3/5] Waiting for solver to complete...${NC}"

MAX_WAIT=$((TIME_LIMIT + 60))  # Add buffer for processing
ELAPSED=0
POLL_INTERVAL=5

while [ $ELAPSED -lt $MAX_WAIT ]; do
    STATUS_RESPONSE=$(curl -s "$SERVER_URL$API_PREFIX/status/$JOB_ID")
    STATUS=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', ''))" 2>/dev/null || echo "")
    
    case $STATUS in
        "completed")
            echo -e "\n${GREEN}✓ Solver completed!${NC}"
            break
            ;;
        "failed")
            echo -e "\n${RED}✗ Solver failed!${NC}"
            ERROR=$(echo "$STATUS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('error', 'Unknown error'))" 2>/dev/null || echo "Unknown error")
            echo "Error: $ERROR"
            exit 1
            ;;
        "running"|"queued")
            printf "."
            ;;
        *)
            if [ $ELAPSED -gt 10 ]; then
                echo -e "\n${RED}ERROR: Unknown status: $STATUS${NC}"
                echo "Response: $STATUS_RESPONSE"
                exit 1
            fi
            printf "."
            ;;
    esac
    
    sleep $POLL_INTERVAL
    ELAPSED=$((ELAPSED + POLL_INTERVAL))
done

if [ "$STATUS" != "completed" ]; then
    echo -e "${RED}ERROR: Solver timed out after ${MAX_WAIT}s${NC}"
    exit 1
fi

# Retrieve result
echo ""
echo -e "${YELLOW}[4/5] Retrieving result...${NC}"

RESULT_RESPONSE=$(curl -s "$SERVER_URL$API_PREFIX/result/$JOB_ID")
RESULT_STATUS=$(echo "$RESULT_RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
tj = data.get('timetable_json', {})
if isinstance(tj, dict):
    print(tj.get('status', 'UNKNOWN'))
else:
    print('UNKNOWN')
" 2>/dev/null || echo "UNKNOWN")

echo "Solver status: $RESULT_STATUS"

# Validate result
echo ""
echo -e "${YELLOW}[5/5] Validating result...${NC}"

# Check solver status
if [ "$RESULT_STATUS" == "OPTIMAL" ] || [ "$RESULT_STATUS" == "FEASIBLE" ]; then
    echo -e "${GREEN}✓ Status: $RESULT_STATUS${NC}"
else
    echo -e "${RED}✗ Unexpected status: $RESULT_STATUS${NC}"
    if [ "$VERBOSE" == "true" ]; then
        echo "Full response:"
        echo "$RESULT_RESPONSE" | python3 -m json.tool
    fi
    exit 1
fi

# Check timetable exists
TIMETABLE_SIZE=$(echo "$RESULT_RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
tj = data.get('timetable_json', {})
if isinstance(tj, dict):
    tt = tj.get('timetable', {})
    print(len(tt) if isinstance(tt, dict) else 0)
else:
    print(0)
" 2>/dev/null || echo "0")

if [ "$TIMETABLE_SIZE" -gt 0 ]; then
    echo -e "${GREEN}✓ Timetable generated: $TIMETABLE_SIZE classes${NC}"
else
    echo -e "${RED}✗ No timetable in result${NC}"
    exit 1
fi

# Check for relaxed constraints
RELAXED=$(echo "$RESULT_RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
tj = data.get('timetable_json', {})
if isinstance(tj, dict):
    ri = tj.get('relaxation_info', {})
    if isinstance(ri, dict):
        rc = ri.get('relaxed_constraints', [])
        print(','.join(rc) if rc else 'none')
    else:
        print('none')
else:
    print('none')
" 2>/dev/null || echo "unknown")

if [ "$RELAXED" == "none" ]; then
    echo -e "${GREEN}✓ No constraints relaxed${NC}"
else
    echo -e "${YELLOW}⚠ Relaxed constraints: $RELAXED${NC}"
fi

# Check solve time
SOLVE_TIME=$(echo "$RESULT_RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
tj = data.get('timetable_json', {})
if isinstance(tj, dict):
    meta = tj.get('meta', {})
    if isinstance(meta, dict):
        print(meta.get('total_time_sec', meta.get('solve_time_seconds', 'unknown')))
    else:
        print('unknown')
else:
    print('unknown')
" 2>/dev/null || echo "unknown")

echo -e "${GREEN}✓ Solve time: ${SOLVE_TIME}s${NC}"

# Check file persistence
echo ""
RESULT_FILE="/Applications/Projects/Timetable/data/results/job_${JOB_ID}.json"
if [ -f "$RESULT_FILE" ]; then
    echo -e "${GREEN}✓ Result persisted to file${NC}"
else
    echo -e "${YELLOW}⚠ Result file not found (may be using Redis only)${NC}"
fi

# Summary
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}  ✓ VERIFICATION PASSED${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "The two-phase solver successfully handled the demo case:"
echo "  • 6 classes, 35 teachers"
echo "  • Status: $RESULT_STATUS"
echo "  • Solve time: ${SOLVE_TIME}s"
echo "  • Relaxed: $RELAXED"
echo ""

if [ "$VERBOSE" == "true" ]; then
    echo ""
    echo -e "${YELLOW}Full result:${NC}"
    echo "$RESULT_RESPONSE" | python3 -m json.tool
fi
