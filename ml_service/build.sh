#!/bin/bash
# Render build script - force pip to use only pre-built wheels
pip install --no-build-isolation --only-binary :all: -r requirements.txt
