#!/usr/bin/env bash
cd "$(dirname "$0")/../backend" && python3 -m pytest -q
