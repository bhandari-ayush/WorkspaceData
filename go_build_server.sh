#!/bin/bash

# Script to build a specified server
# Usage: ./build_server.sh <server_name> [commit_id]

echo "-----------------------------------"
echo "Starting the build process..."
echo "-----------------------------------"

if [ -z "$1" ]; then
  read -p "Enter the server name (e.g., indra): " SERVER_NAME
else
  SERVER_NAME=$1
fi

# Validate server name
if [ -z "$SERVER_NAME" ]; then
  echo "-----------------------------------"
  echo "Error: Server name cannot be empty."
  echo "-----------------------------------"
  exit 1
fi

# Check if a commit ID is provided
COMMIT_ID=$2

echo "-----------------------------------"
echo "Server Name: $SERVER_NAME"
if [ -n "$COMMIT_ID" ]; then
  echo "Commit ID: $COMMIT_ID"
else
  echo "Commit ID: Not provided (defaulting to latest)"
fi
echo "-----------------------------------"

# Define the base directory
BASE_DIR="/home/nutanix/calm-epsilon-shared/src/ces/server"

# Navigate to the server directory
echo "Navigating to the server directory: $BASE_DIR/$SERVER_NAME"
cd "$BASE_DIR/$SERVER_NAME" || { echo "Error: Server directory not found."; exit 1; }

# Remove the server binary if it exists
if [ -f "$BASE_DIR/$SERVER_NAME/server" ]; then
  echo "-----------------------------------"
  echo "Removing existing server binary..."
  rm -f "$BASE_DIR/$SERVER_NAME/server"
  echo "Server binary removed."
  echo "-----------------------------------"
else
  echo "-----------------------------------"
  echo "No existing server binary found. Skipping removal."
  echo "-----------------------------------"
fi

# Clean Go cache
echo "-----------------------------------"
echo "Cleaning Go cache..."
go clean -cache
echo "Go cache cleaned."
echo "-----------------------------------"

# Set GOPRIVATE environment variable
echo "-----------------------------------"
echo "Setting GOPRIVATE environment variable..."
export GOPRIVATE="github.com/ideadevice/goepsilon-client,github.com/nutsnix-core/ntnx-api-go-sdk-internal,github.com/nutanix-core/go-backports/golang.org,github.com/ideadevice/gopolicy-client,github.com/nutanix-core/go-cache,github.com/ideadevice/gamma-libs"
echo "GOPRIVATE environment variable set."
echo "-----------------------------------"

# Fetch dependencies
if [ -n "$COMMIT_ID" ]; then
  if [ "$COMMIT_ID" == "main" ]; then
    echo "-----------------------------------"
    echo "Fetching gamma-libs at branch: main"
    go get github.com/ideadevice/gamma-libs
    echo "Dependencies fetched for branch: main"
    echo "-----------------------------------"
  else
    echo "-----------------------------------"
    echo "Fetching gamma-libs at commit ID: $COMMIT_ID"
    go get github.com/ideadevice/gamma-libs@"$COMMIT_ID"
    echo "Dependencies fetched for commit ID: $COMMIT_ID"
    echo "-----------------------------------"
  fi
else
  echo "-----------------------------------"
  echo "Fetching the latest gamma-libs..."
  go get github.com/ideadevice/gamma-libs
  echo "Dependencies fetched for the latest version."
  echo "-----------------------------------"
fi

# Tidy up Go modules
echo "-----------------------------------"
echo "Tidying up Go modules..."
go mod tidy
echo "Go modules tidied."
echo "-----------------------------------"

# Vendor Go modules
echo "-----------------------------------"
echo "Vendoring Go modules..."
go mod vendor
echo "Go modules vendored."
echo "-----------------------------------"

# Navigate to the CES directory and build the server
echo "-----------------------------------"
echo "Navigating to the CES directory..."
cd /home/nutanix/calm-epsilon-shared/src/ces || { echo "Error: CES directory not found."; exit 1; }

echo "Building the server: $SERVER_NAME"
make build_"$SERVER_NAME"
echo "Build process for $SERVER_NAME completed successfully."
echo "-----------------------------------"

# Copy the binary to the current directory of the script
echo "-----------------------------------"
echo "Copying the binary to the current directory..."
SCRIPT_DIR="/home/nutanix/"
BINARY_PATH="/home/nutanix/calm-epsilon-shared/src/ces/server/$SERVER_NAME/$SERVER_NAME"

if [ -f "$BINARY_PATH" ]; then
  cp "$BINARY_PATH" "$SCRIPT_DIR"
  echo "Binary copied to: $SCRIPT_DIR"
  echo "-----------------------------------"
else
  echo "Error: Binary not found at $BINARY_PATH."
  echo "-----------------------------------"
  exit 1
fi
