$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot\..
python -m pip install --upgrade pip
python -m pip install -r requirements-build.txt
python scripts/build_nuitka.py
