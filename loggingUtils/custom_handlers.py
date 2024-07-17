import logging
import telebot


class TelegramBotHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        with open('data/telegramToken.txt', 'r') as file:
            self.token = file.read()
        self.chat_ids = [359230239, 252404343]

    def emit(self, record: logging.LogRecord):
        bot = telebot.TeleBot(self.token)
        for chat_id in self.chat_ids:
            bot.send_message(
                chat_id,
                self.format(record)
            )


class ClearingFileHandler(logging.FileHandler):
    def __init__(self, filename, **kwargs):
        with open(filename, 'w'):
            pass

        super().__init__(filename, **kwargs)
