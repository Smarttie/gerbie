from dotenv import load_dotenv
import os

# Cargar el archivo .env
load_dotenv()

class DefaultConfig:
    PORT = 3978
    APP_ID = os.environ.get("MicrosoftAppId", "")
    APP_PASSWORD = os.environ.get("MicrosoftAppPassword", "")
