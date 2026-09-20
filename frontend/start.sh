#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
command -v node >/dev/null 2>&1 || { echo "Node.js is not installed. Install Node.js LTS first."; exit 1; }
if [ ! -d node_modules ]; then npm install; fi
[ -f .env ] || cp .env.example .env
npm start
