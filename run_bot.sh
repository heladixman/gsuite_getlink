#!/bin/bash
# Script untuk menjalankan bot di Ubuntu
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

python3 main.py "$@"
