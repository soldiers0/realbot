import logging
import threading
import json
import pickle
import time

from config.cfg import config
from steam.LoginExecutor import LoginExecutor
from loggingUtils.loggingConfig import AccountAdapter, AbstractLoggingClass

from models import Account


class SessionMaintainer(AbstractLoggingClass):
    def __init__(self, account_name):
        self.logger = AccountAdapter(self.logger, extra=Account(account_name).getDict())
        self.account_name = account_name

    def maintainingSteamSession(self, delay=600):
        while True:
            try:
                session = LoginExecutor(self.account_name).getLoggedSession()
                if session is not None:

                    with open(f'data/loggedSessions/{self.account_name}.pkl', 'wb') as file:
                        pickle.dump(session, file, pickle.HIGHEST_PROTOCOL)

                    self.logger.info(f'session reopen')
                if session is None:
                    self.logger.info(f"Can't reopen session")
            except LoginExecutor.CaptchaRequiredException:
                self.logger.critical('captcha required for login')
            except Exception as e:
                self.logger.exception(e)
            time.sleep(delay)


def main(accounts: list[str]):
    for accountName in accounts:
        thread = threading.Thread(target=SessionMaintainer(accountName).maintainingSteamSession)
        thread.start()
        time.sleep(60)


if __name__ == '__main__':
    main(config()['active_accounts'])
    # main(["tihohon"])