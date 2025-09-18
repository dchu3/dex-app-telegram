#!/bin/bash
set -e

echo "🔄 Updating packages..."
apt update -y
apt install -y python3 python3-venv python3-full python3-pip

echo "🐍 Setting up virtual environment..."
cd "$(dirname "$0")"
if [ -d "venv" ]; then
  echo "⚠️  Virtual environment already exists, skipping creation."
else
  python3 -m venv venv
  echo "✅ Virtual environment created."
fi

echo "📦 Activating venv and installing requirements..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt

echo "✅ Dev setup complete!"
echo "To start working, run:"
echo "  source venv/bin/activate"
echo "Then run tests with:"
echo "  pytest"
