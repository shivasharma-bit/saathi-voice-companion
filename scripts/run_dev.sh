#!/usr/bin/env bash
# Convenience script: sets up a venv (if missing), installs deps,
# copies .env.example -> .env (if missing), and starts the server.
set -e

cd "$(dirname "$0")/.."

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate

echo "Installing dependencies..."
pip install -q -r requirements.txt

if [ ! -f ".env" ]; then
  echo "Creating .env from .env.example — remember to add your RIME_API_KEY."
  cp .env.example .env
fi

echo "Starting Saathi on http://localhost:8000 ..."
uvicorn backend.main:app --reload
