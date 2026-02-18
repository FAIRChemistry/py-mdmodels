#!/bin/bash

# Default Python version
PYTHON_VERSION="3.12"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --python=*)
            PYTHON_VERSION="${1#--python=}"
            shift 1
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--python=VERSION]"
            exit 1
            ;;
    esac
done

# Run tests with specified Python version
echo "Building Docker image with Python $PYTHON_VERSION"
docker build --build-arg PYTHON_VERSION=$PYTHON_VERSION -t mdmodels .

echo "Running tests with Docker container"
docker run \
    -v ${PWD}/mdmodels:/app/mdmodels \
    -v ${PWD}/tests:/app/tests \
    mdmodels

echo "Tests completed"