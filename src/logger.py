from loguru import logger
import sys

# Configure Loguru
# Remove default handler to avoid duplicate logs if reloaded
logger.remove()

# Add a formatted handler
# <green>{time}</green> : Time
# <level>{level}</level> : Lvl
# <cyan>{extra[name]}</cyan> : Bound name (module)
# <cyan>{function}</cyan>:<cyan>{line}</cyan> : Func/Line
# <level>{message}</level> : Msg
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{extra[name]}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO"
)

def get_logger(name: str):
    """
    Returns a loguru logger bound with the specific module name.
    This maintains compatibility with the previous get_logger(name) pattern.
    """
    # Bind the 'name' key to the extra dict so it shows up in the format
    return logger.bind(name=name)
