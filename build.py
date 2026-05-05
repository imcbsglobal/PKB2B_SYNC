import os
import shutil
import subprocess
import sys


DIST_FOLDER = "PKB2B_Sync"     # final folder to give users


def safe_rmtree(path):
    """Remove a directory tree, ignoring errors (e.g. locked files on Windows)."""
    if os.path.exists(path):
        try:
            shutil.rmtree(path)
        except Exception as e:
            print(f"  [WARN] Could not remove '{path}': {e}")
            print(f"  [WARN] Please delete it manually if needed.")


def build():
    # ── 1. Clean previous output ──────────────────────────────────
    safe_rmtree(DIST_FOLDER)
    safe_rmtree("build")
    for f in [f for f in os.listdir(".") if f.endswith(".spec")]:
        os.remove(f)

    # ── 2. Install PyInstaller (if not present) ───────────────────
    print("[BUILD] Installing PyInstaller...")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "pyinstaller"],
        stdout=subprocess.DEVNULL,
    )

    # ── 3. Build the exe ──────────────────────────────────────────
    print("[BUILD] Building exe...")
    subprocess.check_call([
        "pyinstaller",
        "--onefile",
        "--clean",
        "--name", "PKB2B_Sync",
        "--distpath", DIST_FOLDER,
        "--workpath", "build",
        "--specpath", "build",
        "--windowed",
        "sync.py",
    ])

    # ── 4. Copy config.json into the dist folder ──────────────────
    shutil.copy("config.json", os.path.join(DIST_FOLDER, "config.json"))

    # ── 5. Create a README for the end-user ───────────────────────
    readme = os.path.join(DIST_FOLDER, "README.txt")
    with open(readme, "w") as f:
        f.write(
            "PKB2B Sync Tool\n"
            "================\n\n"
            "Steps to use:\n"
            "1. Open  config.json  in Notepad.\n"
            "2. Set  \"database\"  to your SQL Anywhere database engine name.\n"
            "3. Set  \"base_url\"  to the server API address provided to you.\n"
            "4. Double-click  PKB2B_Sync.exe  to start syncing.\n\n"
            "Note: The SQL Anywhere database must be running before you start the sync.\n"
        )

    # ── 6. Clean up build artifacts ───────────────────────────────
    safe_rmtree("build")

    print()
    print("=" * 50)
    print("  BUILD COMPLETE!")
    print("=" * 50)
    print()
    print(f"  Distribute the entire '{DIST_FOLDER}' folder to users.")
    print(f"  Contents:")
    for item in sorted(os.listdir(DIST_FOLDER)):
        size = os.path.getsize(os.path.join(DIST_FOLDER, item))
        print(f"    - {item}  ({size:,} bytes)")
    print()


if __name__ == "__main__":
    build()
