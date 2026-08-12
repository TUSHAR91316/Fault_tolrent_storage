#!/usr/bin/env bash
set -e

echo "============================================================"
echo "  Building Fault-Tolerant Storage Release Packages & Docker"
echo "============================================================"

echo "1. Building Python Wheel & Source Packages..."
python3 -m pip install --upgrade build setuptools wheel
python3 -m build

echo ""
echo "2. Building Multi-Stage Production Docker Images..."
docker build -t tushar/fts-coordinator:latest -t tushar/fts-coordinator:v1.0.0 ./coordinator
docker build -t tushar/fts-node:latest -t tushar/fts-node:v1.0.0 ./node
docker build -t tushar/fts-ai-analyzer:latest -t tushar/fts-ai-analyzer:v1.0.0 ./ai

echo ""
echo "============================================================"
echo "  Release Package & Docker Image Build Complete!"
echo "============================================================"
