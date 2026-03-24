#!/bin/bash

# NHW Apartment Scraper Runner

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$DIR"

echo "Activating virtual environment..."
source venv/bin/activate

echo "Starting the scraper..."
python3 scraper.py
