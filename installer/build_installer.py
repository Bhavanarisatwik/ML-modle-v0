"""
DecoyVerse Agent Installer Builder
Run this script to create the .exe installer using PyInstaller
"""

import subprocess
import sys
import os

def main():
    # Ensure PyInstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    
    # Get the directory of this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    installer_script = os.path.join(script_dir, "decoyverse_installer.py")
    icon_path = os.path.join(script_dir, "icon.ico")
    
    # Build command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--console",  # Show console for progress
        "--name", "DecoyVerse-Installer",
        "--clean",
    ]
    
    # Add icon if exists
    if os.path.exists(icon_path):
        cmd.extend(["--icon", icon_path])
    
    cmd.append(installer_script)
    
    print("Building DecoyVerse Installer...")
    print(f"Command: {' '.join(cmd)}")
    
    subprocess.run(cmd, cwd=script_dir)
    
    print("\n" + "="*50)
    print("Build complete!")
    print(f"Find your .exe at: {os.path.join(script_dir, 'dist', 'DecoyVerse-Installer.exe')}")
    print("="*50)

if __name__ == "__main__":
    main()
