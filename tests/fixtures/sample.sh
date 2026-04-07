#!/bin/bash
# Sample Bash script for graphify test fixture

source lib/utils.sh
. ./helpers.sh

# Global variables
LOG_DIR="/var/log/app"
readonly MAX_RETRIES=3

# Simple function using name() syntax
log_message() {
    local level="$1"
    local msg="$2"
    echo "[$level] $(date): $msg" >> "$LOG_DIR/app.log"
}

# Function using 'function' keyword
function validate_input {
    local input="$1"
    if [[ -z "$input" ]]; then
        log_message "ERROR" "Empty input"
        return 1
    fi
    return 0
}

# Function that calls other functions
function process_file {
    local filepath="$1"
    validate_input "$filepath"
    if [[ $? -ne 0 ]]; then
        return 1
    fi
    log_message "INFO" "Processing $filepath"
    transform_data "$filepath"
}

# Another function for call-graph testing
transform_data() {
    local file="$1"
    log_message "DEBUG" "Transforming $file"
}

# Main execution
process_file "/tmp/data.csv"
