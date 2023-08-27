#!/bin/bash

# Remove .git directory
if [ -d ".git" ]; then
  rm -rf .git
  echo ".git directory removed."
else
  echo ".git directory not found."
fi

# Remove test.txt file
if [ -f "test.txt" ]; then
  rm test.txt
  echo "test.txt file removed."
else
  echo "test.txt file not found."
fi

# Run pytest command
python3 -m pytest tests/.