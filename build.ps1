# build.ps1
Write-Host "Building Daemon executable..."
py -m PyInstaller --noconfirm --name Daemon --windowed --add-data "assets;assets" --add-data "src;src" daemon.py
Write-Host "Build complete! Executable is in the dist/Daemon folder."
