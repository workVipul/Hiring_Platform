import shutil
from pathlib import Path

src = Path("C:/Users/Wissen/.gemini/antigravity/brain/5e911f9c-2a10-446a-8344-9f73a220728b/media__1779346912455.png")
dest_dir = Path("C:/Users/Wissen/Hiring_Platform/backend/app")
dest = dest_dir / "wissen_logo.png"

try:
    if src.exists():
        shutil.copy(src, dest)
        print("LOGO COPIED SUCCESSFULLY TO:", dest)
    else:
        print("SOURCE LOGO FILE NOT FOUND AT:", src)
except Exception as e:
    print("ERROR COPYING LOGO:", e)
