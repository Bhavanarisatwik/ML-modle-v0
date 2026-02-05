"""
DecoyVerse Agent Installer
Standalone executable installer for Windows

Usage:
  1. Run directly - will prompt for Node ID and API Key
  2. Run with config file: DecoyVerse-Installer.exe --config config.json
  3. Run with arguments: DecoyVerse-Installer.exe --node-id xxx --api-key yyy
"""

import os
import sys
import json
import ctypes
import urllib.request
import subprocess
import argparse
import time

# Configuration
INSTALL_DIR = r"C:\DecoyVerse"
GITHUB_REPO = "https://raw.githubusercontent.com/Bhavanarisatwik/ML-modle-v0/main"
BACKEND_URL = "https://ml-modle-v0-1.onrender.com/api"
EXPRESS_BACKEND_URL = "https://decoyverse-v2.onrender.com/api"
ML_SERVICE_URL = "https://ml-modle-v0-1.onrender.com"

AGENT_FILES = [
    "agent.py",
    "agent_setup.py", 
    "agent_config.py",
    "file_monitor.py",
    "alert_sender.py"
]

REQUIRED_PACKAGES = ["requests", "watchdog", "psutil"]


def is_admin():
    """Check if running as administrator"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def run_as_admin():
    """Re-launch as administrator"""
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1
    )
    sys.exit()


def print_banner(node_name=""):
    """Print installer banner"""
    os.system('cls' if os.name == 'nt' else 'clear')
    print()
    print("=" * 55)
    print("     🕷️  DecoyVerse Agent Installer v2.0  🕷️")
    if node_name:
        print(f"     Node: {node_name}")
    print("=" * 55)
    print()


def print_step(step, total, message):
    """Print step progress"""
    print(f"[{step}/{total}] {message}")


def print_success(message):
    """Print success message"""
    print(f"      ✓ {message}")


def print_error(message):
    """Print error message"""
    print(f"      ✗ {message}")


def download_file(url, dest_path):
    """Download a file from URL"""
    try:
        urllib.request.urlretrieve(url, dest_path)
        return True
    except Exception as e:
        print_error(f"Download failed: {e}")
        return False


def find_python():
    """Find Python executable"""
    # Try common locations
    possible_paths = [
        "python",
        "python3",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python311\python.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python310\python.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python312\python.exe"),
        r"C:\Python311\python.exe",
        r"C:\Python310\python.exe",
    ]
    
    for python_path in possible_paths:
        try:
            result = subprocess.run(
                [python_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if "Python 3" in result.stdout or "Python 3" in result.stderr:
                return python_path
        except:
            continue
    
    return None


def get_pythonw(python_cmd: str) -> str:
    """Get pythonw.exe path if available, fallback to python.exe"""
    if not python_cmd:
        return "pythonw.exe"
    if python_cmd.lower().endswith("python.exe"):
        pythonw = python_cmd[:-10] + "pythonw.exe"
        if os.path.exists(pythonw):
            return pythonw
    return python_cmd


def install_packages(python_cmd):
    """Install required Python packages"""
    try:
        subprocess.run(
            [python_cmd, "-m", "pip", "install", "--quiet", "--upgrade", "pip"],
            capture_output=True
        )
        subprocess.run(
            [python_cmd, "-m", "pip", "install", "--quiet"] + REQUIRED_PACKAGES,
            capture_output=True
        )
        return True
    except Exception as e:
        print_error(f"Package installation failed: {e}")
        return False


def write_config(config_data):
    """Write configuration file without BOM"""
    config_path = os.path.join(INSTALL_DIR, "agent_config.json")
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=2)
    return True


def register_scheduled_task(pythonw_cmd: str) -> bool:
    """Create scheduled task to run agent in background"""
    try:
        task_name = "DecoyVerseAgent"
        agent_path = os.path.join(INSTALL_DIR, "agent.py")
        # Delete old task if exists
        subprocess.run([
            "schtasks", "/Delete", "/TN", task_name, "/F"
        ], capture_output=True)

        # Create task to run at logon and startup
        create_cmd = (
            f"schtasks /Create /TN {task_name} /TR \"\"{pythonw_cmd}\" \"{agent_path}\"\" "
            f"/SC ONLOGON /RL HIGHEST /F"
        )
        subprocess.run(create_cmd, shell=True, check=True, capture_output=True)

        # Add startup trigger (separate trigger)
        create_startup = (
            f"schtasks /Create /TN {task_name} /TR \"\"{pythonw_cmd}\" \"{agent_path}\"\" "
            f"/SC ONSTART /RL HIGHEST /F"
        )
        subprocess.run(create_startup, shell=True, check=True, capture_output=True)
        return True
    except Exception as e:
        print_error(f"Failed to create scheduled task: {e}")
        return False


def get_config_interactive():
    """Get configuration interactively from user"""
    print("Please enter your node credentials:")
    print("(You can find these in your DecoyVerse dashboard)")
    print()
    
    node_id = input("  Node ID: ").strip()
    api_key = input("  API Key: ").strip()
    node_name = input("  Node Name (optional): ").strip() or "DecoyVerse Node"
    
    if not node_id or not api_key:
        print_error("Node ID and API Key are required!")
        return None
    
    return {
        "node_id": node_id,
        "node_api_key": api_key,
        "node_name": node_name,
        "os_type": "windows",
        "backend_url": BACKEND_URL,
        "express_backend_url": EXPRESS_BACKEND_URL,
        "ml_service_url": ML_SERVICE_URL,
        "deployment_config": {
            "initial_decoys": 3,
            "initial_honeytokens": 5,
            "deploy_path": None
        }
    }


def main():
    """Main installer function"""
    parser = argparse.ArgumentParser(description="DecoyVerse Agent Installer")
    parser.add_argument("--config", help="Path to config JSON file")
    parser.add_argument("--node-id", help="Node ID")
    parser.add_argument("--api-key", help="Node API Key")
    parser.add_argument("--node-name", default="DecoyVerse Node", help="Node name")
    parser.add_argument("--no-run", action="store_true", help="Don't run agent after install")
    args = parser.parse_args()
    
    # Check for admin
    if not is_admin():
        print_banner()
        print("[!] Requesting Administrator privileges...")
        print("    Please click YES on the UAC prompt...")
        time.sleep(1)
        run_as_admin()
        return
    
    # Get configuration
    config = None
    
    if args.config and os.path.exists(args.config):
        with open(args.config, 'r') as f:
            config = json.load(f)
    elif args.node_id and args.api_key:
        config = {
            "node_id": args.node_id,
            "node_api_key": args.api_key,
            "node_name": args.node_name,
            "os_type": "windows",
            "backend_url": BACKEND_URL,
            "express_backend_url": EXPRESS_BACKEND_URL,
            "ml_service_url": ML_SERVICE_URL,
            "deployment_config": {
                "initial_decoys": 3,
                "initial_honeytokens": 5,
                "deploy_path": None
            }
        }
    
    # Print banner
    print_banner(config.get("node_name", "") if config else "")
    print("[OK] Running with Administrator privileges")
    print()
    
    # Interactive mode if no config
    if not config:
        config = get_config_interactive()
        if not config:
            input("\nPress Enter to exit...")
            return
        print()
    
    total_steps = 6
    
    # Step 1: Create directory
    print_step(1, total_steps, "Creating installation directory...")
    try:
        os.makedirs(INSTALL_DIR, exist_ok=True)
        os.chdir(INSTALL_DIR)
        print_success(f"Directory: {INSTALL_DIR}")
    except Exception as e:
        print_error(f"Failed to create directory: {e}")
        input("\nPress Enter to exit...")
        return
    
    # Step 2: Check Python
    print_step(2, total_steps, "Checking Python installation...")
    python_cmd = find_python()
    if not python_cmd:
        print_error("Python 3.10+ not found!")
        print("      Please install Python from https://python.org")
        input("\nPress Enter to exit...")
        return
    pythonw_cmd = get_pythonw(python_cmd)
    print_success(f"Found: {python_cmd}")
    print_success(f"Background runner: {pythonw_cmd}")
    
    # Step 3: Write config
    print_step(3, total_steps, "Writing agent configuration...")
    if write_config(config):
        print_success("Config saved!")
    else:
        print_error("Failed to write config")
        input("\nPress Enter to exit...")
        return
    
    # Step 4: Download files
    print_step(4, total_steps, "Downloading agent files...")
    for filename in AGENT_FILES:
        url = f"{GITHUB_REPO}/{filename}"
        dest = os.path.join(INSTALL_DIR, filename)
        if download_file(url, dest):
            print_success(f"Downloaded: {filename}")
        else:
            print_error(f"Failed to download: {filename}")
    
    # Step 5: Install dependencies
    print_step(5, total_steps, "Installing Python dependencies...")
    if install_packages(python_cmd):
        print_success("Dependencies installed!")
    else:
        print_error("Some packages may have failed to install")
    
    # Step 6: Register auto-start task and run agent
    if args.no_run:
        print_step(6, total_steps, "Registering auto-start task...")
        register_scheduled_task(pythonw_cmd)
        print_success("Auto-start enabled")
        print()
        print("=" * 55)
        print("  To start the agent, run:")
        print(f"    cd {INSTALL_DIR}")
        print("    pythonw agent.py")
        print("=" * 55)
    else:
        print_step(6, total_steps, "Registering auto-start task...")
        if register_scheduled_task(pythonw_cmd):
            print_success("Auto-start enabled")
        print_step(6, total_steps, "Starting DecoyVerse agent in background...")
        print()
        print("=" * 55)
        print()
        try:
            subprocess.run(["schtasks", "/Run", "/TN", "DecoyVerseAgent"], check=True)
            print_success("Agent started in background")
        except Exception as e:
            print_error(f"Failed to run agent: {e}")
    
    print()
    print("=" * 55)
    print("  Installation complete!")
    print("  To restart the agent:")
    print("    Start-ScheduledTask -TaskName \"DecoyVerseAgent\"")
    print("=" * 55)
    print()
    input("Press Enter to exit...")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        input("Press Enter to exit...")
