"""py2app setup for Card-Sharp.

Build:
    python setup.py py2app
"""
from setuptools import setup

APP = ["card_sharp/main.py"]
DATA_FILES = [("assets", ["assets/table-badge.png"])]
OPTIONS = {
    "argv_emulation": False,
    "iconfile": "assets/icon.icns",
    "packages": ["card_sharp"],
    "includes": ["sqlite3", "tkinter"],
    "plist": {
        "CFBundleName": "Card-Sharp",
        "CFBundleDisplayName": "Card-Sharp",
        "CFBundleIdentifier": "com.saltz.cardsharp",
        "CFBundleVersion": "0.6.0",
        "CFBundleShortVersionString": "0.6.0",
        "NSHumanReadableCopyright": "© 2026 Saltz",
        "LSMinimumSystemVersion": "10.15",
        "NSHighResolutionCapable": True,
    },
}

setup(
    app=APP,
    name="Card-Sharp",
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
