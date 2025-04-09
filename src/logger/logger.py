import logging

# Включаем логирование
logger = logging.getLogger(__name__)

def setup_logger():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )