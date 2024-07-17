import base64
import pickle
import time

from loggingUtils import loggingConfig
import requests
import rsa
from getOneTimeCode import getOneTimeCode
from models import Account


class LoginExecutor(loggingConfig.AbstractLoggingClass):
    def __init__(self, accountName: str):
        self.account = Account(accountName)
        self.logger = loggingConfig.AccountAdapter(self.logger, extra=self.account.getDict())

    class CaptchaRequiredException(Exception):
        pass

    def getAccountSession(self):
        with open(f"data/loggedSessions/{self.account.username}.pkl", 'rb') as file:
            return pickle.load(file)

    def getLoggedSession(self, saveSession=True, newSessionOnly=True, debug=False):
        steamUsername = self.account.username
        steamPassword = self.account.password
        steamUrl = 'https://steamcommunity.com/'
        session = requests.Session()
        # with open(self.accountData['proxy']) as file:
        # 	proxyDict = json.load(file)
        proxyDict = {}
        if proxyDict:
            proxies = {
                'https': f"http://{proxyDict['username']}:{proxyDict['password']}@{proxyDict['adress']}",
                'http': f"http://{proxyDict['username']}:{proxyDict['password']}@{proxyDict['adress']}"
            }
            session.proxies = proxies
        for i in range(3):
            try:
                key_response = session.post(steamUrl + '/login/getrsakey/', data={'username': steamUsername})
                key_response = key_response.json()
                break
            except Exception as e:
                if i == 2 and debug:
                    self.logger.error(f'could not log in (failed to recieve rsa key) - {e}')
                    return None
                time.sleep(3)

        rsa_mod = int(key_response['publickey_mod'], 16)
        rsa_exp = int(key_response['publickey_exp'], 16)
        rsaKey = rsa.PublicKey(rsa_mod, rsa_exp)
        encryptedPassword = base64.b64encode(rsa.encrypt(steamPassword.encode('utf-8'), rsaKey))
        loginData = {
            'password': encryptedPassword,
            'username': steamUsername,
            'twofactorcode': getOneTimeCode(steamUsername),
            'emailauth': '',
            'loginfriendlyname': '',
            'captchagid': '-1',
            'captcha_text': '',
            'emailsteamid': '',
            'rsatimestamp': key_response['timestamp'],
            'remember_login': 'true',
            'donotcache': str(int(time.time() * 1000))
        }

        parameters = None

        for i in range(3):
            try:
                response = session.post(steamUrl + '/login/dologin', data=loginData).json()
                if not response.get('success') and 'captcha' in response.get('message'):
                    raise self.CaptchaRequiredException
            except self.CaptchaRequiredException:
                raise self.CaptchaRequiredException
            except Exception as e:
                if i == 2 and debug:
                    print(f'could not execute login for {steamUsername} - {e}')
                    return None
                time.sleep(5)
                continue
            # save login
            if 'transfer_parameters' not in response:
                if i == 2 and debug:
                    self.logger.error(f'could not execute log in (no parameters)')
                    return None
                time.sleep(5)
                continue
            else:
                parameters = response['transfer_parameters']
                break

        for url in response['transfer_urls']:
            for i in range(3):
                try:
                    session.post(url, parameters)
                    break
                except Exception as e:
                    if i == 2 and debug:
                        self.logger.error(f'could not execute log in (failed to transfer parameters to {url})')

        sessionid = session.cookies.get_dict()['sessionid']
        community_domain = 'steamcommunity.com'
        store_domain = 'store.steampowered.com'
        community_cookie = {"name": "sessionid",
                            "value": sessionid,
                            "domain": community_domain}
        store_cookie = {"name": "sessionid",
                        "value": sessionid,
                        "domain": store_domain}
        session.cookies.set(**community_cookie)
        session.cookies.set(**store_cookie)

        if saveSession:
            with open(f'data/loggedSessions/{steamUsername}.pkl', 'wb') as file:
                pickle.dump(session, file, pickle.HIGHEST_PROTOCOL)

        return session

    def transferCookies(self, originSession, recipientSession):
        cookies = [
            {'name': c.name, 'value': c.value, 'domain': c.domain, 'path': c.path}
            for c in originSession.cookies
        ]

        for cookie in cookies:
            recipientSession.cookies.set(**cookie)