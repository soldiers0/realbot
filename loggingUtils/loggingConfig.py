import logging.config
import os
import __main__


class AccountAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        return f'{msg} from {self.extra["steamUsername"]}', kwargs


class AbstractLoggingClass:
    # logger with name corresponding to
    logger = logging.getLogger(os.path.basename(__main__.__file__).split('.')[0])


LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,

    'formatters': {
        'default_formatter': {
            'format': '[%(levelname)s:%(asctime)s] %(message)s'
        },
    },

    'handlers': {
        'stream_handler': {
            'class': 'logging.StreamHandler',
            'formatter': 'default_formatter',
            'level': 'DEBUG'
        },

        'login_file_handler': {
            'class': 'loggingUtils.custom_handlers.ClearingFileHandler',
            'formatter': 'default_formatter',
            'filename': 'data/logs/login_logs.log',
            'level': 'INFO',
            'encoding': 'utf-8',
        },

        'plznomarket_file_handler': {
            'class': 'loggingUtils.custom_handlers.ClearingFileHandler',
            'formatter': 'default_formatter',
            'filename': 'data/logs/plznomarket_logs.log',
            'level': 'INFO',
            'encoding': 'utf-8',
        },

        'csmoney_file_handler': {
            'class': 'loggingUtils.custom_handlers.ClearingFileHandler',
            'formatter': 'default_formatter',
            'filename': 'data/logs/csmoney_logs.log',
            'level': 'INFO',
            'encoding': 'utf-8',
        },

        'parser_file_handler': {
            'class': 'loggingUtils.custom_handlers.ClearingFileHandler',
            'formatter': 'default_formatter',
            'filename': 'data/logs/parser_logs.log',
            'level': 'INFO',
            'encoding': 'utf-8',
        },

        'inventory_file_handler': {
            'class': 'loggingUtils.custom_handlers.ClearingFileHandler',
            'formatter': 'default_formatter',
            'filename': 'data/logs/inventory_logs.log',
            'level': 'INFO',
            'encoding': 'utf-8',
        },

        'buying_file_handler': {
            'class': 'loggingUtils.custom_handlers.ClearingFileHandler',
            'formatter': 'default_formatter',
            'filename': 'data/logs/buying_logs.log',
            'level': 'INFO',
            'encoding': 'utf-8',
        },

        'withdraw_file_handler': {
            'class': 'loggingUtils.custom_handlers.ClearingFileHandler',
            'formatter': 'default_formatter',
            'filename': 'data/logs/withdraw_logs.log',
            'level': 'INFO',
            'encoding': 'utf-8',
        },

        'request_file_handler': {
            'class': 'loggingUtils.custom_handlers.ClearingFileHandler',
            'formatter': 'default_formatter',
            'filename': 'data/logs/request_logs.log',
            'level': 'INFO',
            'encoding': 'utf-8',
        },

        'telegram_handler': {
            'class': 'loggingUtils.custom_handlers.TelegramBotHandler',
            'formatter': 'default_formatter',
            'level': 'CRITICAL'
        }
    },

    'loggers': {
        'inventoryHandler': {
            'handlers': ['stream_handler', 'inventory_file_handler', 'telegram_handler'],
            'level': 'DEBUG',
            'propagate': True
        },
        'mainParser': {
            'handlers': ['stream_handler', 'parser_file_handler'],
            'level': 'DEBUG',
            'propagate': True
        },
        'steamSessionThread': {
            'handlers': ['stream_handler', 'login_file_handler', 'telegram_handler'],
            'level': 'DEBUG',
            'propagate': True
        },
        'run_csm_parser': {
            'handlers': ['stream_handler', 'csmoney_file_handler', 'telegram_handler'],
            'level': 'DEBUG',
            'propagate': True
        },
        'run_buyers': {
            'handlers': ['stream_handler', 'buying_file_handler', 'telegram_handler'],
            'level': 'DEBUG',
            'propagate': True
        },
        'run_steam_parser': {
            'handlers': ['stream_handler', 'parser_file_handler', 'telegram_handler'],
            'level': 'DEBUG',
            'propagate': True
        },
        'requestHandler':{
            'handlers': ['stream_handler', 'telegram_handler', 'request_file_handler'],
            'level': 'DEBUG',
            'propagate': True
        },
        'test': {
            'handlers': ['stream_handler', 'telegram_handler'],
            'level': 'DEBUG',
            'propagate': True
        },
        'run_withdrawal_parser': {
            'handlers': ['stream_handler', 'telegram_handler', 'withdraw_file_handler'],
            'level': 'DEBUG',
            'propagate': True
        },
        'plznomarket': {
            'handlers': ['stream_handler', 'telegram_handler', 'plznomarket_file_handler'],
            'level': 'DEBUG',
            'propagate': True
        }
    }
}

logging.config.dictConfig(LOGGING_CONFIG)