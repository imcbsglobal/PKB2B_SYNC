import os
import shutil
import subprocess
import sys


DIST_FOLDER = "PKB2B_Sync"


def safe_rmtree(path):
    if os.path.exists(path):
        try:
            shutil.rmtree(path)
        except Exception as e:
            print(f"  [WARN] Could not remove '{path}': {e}")


def make_ico():
    from PIL import Image
    img = Image.open("pk.png").convert("RGBA")
    img.save("pk.ico", format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])
    print("[BUILD] pk.ico created from pk.png")


def build():
    # ── 1. Clean previous output ──────────────────────────────────
    safe_rmtree(DIST_FOLDER)
    safe_rmtree("build")
    for f in [f for f in os.listdir(".") if f.endswith(".spec")]:
        os.remove(f)

    # ── 2. Install dependencies ───────────────────────────────────
    print("[BUILD] Installing PyInstaller and Pillow...")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "pyinstaller", "pillow"],
        stdout=subprocess.DEVNULL,
    )

    # ── 3. Convert pk.png → pk.ico ────────────────────────────────
    make_ico()
    ico_path = os.path.abspath("pk.ico")

    # ── 4. Build the exe ──────────────────────────────────────────
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
        "--icon", ico_path,
        "sync.py",
    ])

    # ── 5. Copy config.json into the dist folder ──────────────────
    shutil.copy("config.json", os.path.join(DIST_FOLDER, "config.json"))

    # ── 6. Create a README for the end-user ───────────────────────
    readme = os.path.join(DIST_FOLDER, "README.txt")
    with open(readme, "w") as f:
        f.write(
            "PKB2B Sync Tool\n"
            "================\n\n"
            "Steps to use:\n"
            "1. Open  config.json  in Notepad.\n"
            "2. Set  \"dsn\"  to your SQL Anywhere DSN name.\n"
            "3. Set  \"base_url\"  to the server API address provided to you.\n"
            "4. Double-click  PKB2B_Sync.exe  to start syncing.\n\n"
            "Note: The SQL Anywhere database must be running before you start the sync.\n"
        )

    # ── 7. Clean up build artifacts ───────────────────────────────
    safe_rmtree("build")
    if os.path.exists("pk.ico"):
        os.remove("pk.ico")

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
