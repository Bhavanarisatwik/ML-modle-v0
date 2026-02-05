# DecoyVerse Installer Builder

## 🎯 Two Installation Methods

### **Method 1: Web-Based Auto-Installer (Recommended)**
Users download pre-configured ZIP from dashboard - **NO .exe BUILDING NEEDED**

**Flow:**
1. User clicks "Download Agent" in dashboard
2. Backend generates ZIP with pre-configured credentials
3. User extracts and runs `install.ps1`
4. Agent auto-installs and deploys decoys

**See:** `AGENT_AUTO_INSTALLER_GUIDE.md` in DecoyVerse-v2 folder

---

### **Method 2: Standalone .exe (Advanced)**
Build a single `.exe` file for offline distribution

## Quick Build (.exe Method)

```bash
cd installer
pip install pyinstaller
python build_installer.py
```

The `.exe` will be created in `installer/dist/DecoyVerse-Installer.exe`

## .exe Usage Options

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

## Distribution Options

### Option 1: Web Download (Easiest)
**Use the auto-installer system** - users download from your dashboard.

### Option 2: GitHub Releases
After building:
1. Go to your GitHub repository
2. Click "Releases" → "Create a new release"
3. Upload `DecoyVerse-Installer.exe`
4. Users download from releases page

### Option 3: Direct Distribution
- Email the `.exe` file
- USB drive
- Shared network folder
- Cloud storage (Google Drive, Dropbox)

---

## Comparison

| Feature | Web Auto-Installer | Standalone .exe |
|---------|-------------------|-----------------|
| **Pre-configured** | ✅ Yes | ❌ No (user enters credentials) |
| **File size** | Small ZIP (~50KB) | Large exe (~10MB) |
| **Updates** | Always latest | Must rebuild |
| **User experience** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Distribution** | Via web dashboard | Manual file sharing |
| **Best for** | Most users | Offline environments |

---

## Recommendation

**Use Method 1 (Web Auto-Installer)** for 99% of cases:
- Better UX (pre-configured)
- Smaller downloads
- Always up-to-date
- Easier to maintain

**Use Method 2 (.exe)** only if:
- Deploying to air-gapped systems (no internet)
- Need single-file distribution
- Want offline installation capability

