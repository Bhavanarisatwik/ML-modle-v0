# DecoyVerse Installer Builder

This folder contains scripts to build a standalone `.exe` installer for the DecoyVerse Agent.

## Quick Build

```bash
cd installer
pip install pyinstaller
python build_installer.py
```

The `.exe` will be created in `installer/dist/DecoyVerse-Installer.exe`

## Usage Options

### 1. Interactive Mode (Double-click)
Just run the `.exe` - it will prompt for Node ID and API Key.

### 2. With Config File
```
DecoyVerse-Installer.exe --config agent_config.json
```

### 3. With Command Line Arguments
```
DecoyVerse-Installer.exe --node-id node-xxx --api-key nk_yyy --node-name "My PC"
```

### 4. Install Only (Don't Run Agent)
```
DecoyVerse-Installer.exe --node-id node-xxx --api-key nk_yyy --no-run
```

## Adding an Icon

Place an `icon.ico` file in this folder before building to use a custom icon.

## Distribution

After building, you can:
1. Upload to GitHub Releases
2. Host on your own server
3. Distribute directly to users

The backend can provide a download link that includes the pre-configured `.exe` or bundle the config with it.
