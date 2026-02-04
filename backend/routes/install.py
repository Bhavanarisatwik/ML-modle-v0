"""
Installer Routes - Serve agent installation scripts
"""

from fastapi import APIRouter, Response
from pathlib import Path

router = APIRouter(prefix="/install", tags=["install"])

INSTALLERS_DIR = Path(__file__).parent.parent / "installers"


@router.get("/windows")
async def get_windows_installer():
    """Download Windows PowerShell installer script"""
    script_path = INSTALLERS_DIR / "install_windows.ps1"
    
    if not script_path.exists():
        return Response(
            content="# Installer not found",
            media_type="text/plain",
            status_code=404
        )
    
    content = script_path.read_text(encoding="utf-8")
    return Response(
        content=content,
        media_type="text/plain",
        headers={
            "Content-Disposition": "attachment; filename=install_decoyverse.ps1"
        }
    )


@router.get("/linux")
async def get_linux_installer():
    """Download Linux bash installer script"""
    script_path = INSTALLERS_DIR / "install_linux.sh"
    
    if not script_path.exists():
        return Response(
            content="# Installer not found",
            media_type="text/plain",
            status_code=404
        )
    
    content = script_path.read_text(encoding="utf-8")
    return Response(
        content=content,
        media_type="text/plain",
        headers={
            "Content-Disposition": "attachment; filename=install_decoyverse.sh"
        }
    )


@router.get("/macos")
async def get_macos_installer():
    """Download macOS bash installer script"""
    script_path = INSTALLERS_DIR / "install_macos.sh"
    
    if not script_path.exists():
        return Response(
            content="# Installer not found",
            media_type="text/plain",
            status_code=404
        )
    
    content = script_path.read_text(encoding="utf-8")
    return Response(
        content=content,
        media_type="text/plain",
        headers={
            "Content-Disposition": "attachment; filename=install_decoyverse.sh"
        }
    )
