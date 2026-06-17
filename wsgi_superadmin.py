import os
from dotenv import load_dotenv
from superadmin_app import app as application

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv()
if os.path.exists(os.path.join(BASE_DIR, ".env")):
    with open(os.path.join(BASE_DIR, ".env"), "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

if __name__ == "__main__":
    port = int(os.environ.get("SUPERADMIN_PORT", 8080))
    application.run(host="0.0.0.0", port=port)
