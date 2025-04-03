import logging

# Включаем логирование
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

def error(self, msg, *args, **kwargs):
    self.log(logging.ERROR, msg, *args, **kwargs)