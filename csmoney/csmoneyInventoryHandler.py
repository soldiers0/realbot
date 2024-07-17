import json

from loggingUtils import loggingConfig
import requests
from tools.itemTools import getHash
from config.cfg import config


class CsmInventoryHandler(loggingConfig.AbstractLoggingClass):
    def __init__(self, accountName):
        self.logger = loggingConfig.AccountAdapter(self.logger, {'steamUsername': accountName})
        self.accountName = accountName
        self.cookies = []
        self._loadCookies()
        self.rate = config()['dollarToEuroExchangeRate']

        self.session = requests.Session()

        for cookie in self.cookies:
            if cookie == 'expired':
                continue

            for key in ['httpOnly', 'sameSite']:
                if key in cookie:
                    cookie.pop(key)
            self.session.cookies.set(**cookie)

        self._setInventory()

    def _loadCookies(self):
        with open(f'data/loggedSessions/{self.accountName}Csmoney.json', 'r') as file:
            self.cookies = json.load(file)

    def _setCookiesExpired(self):
        self.cookies = ['expired']

        with open(f'data/loggedSessions/{self.accountName}Csmoney.json', 'w') as file:
            json.dump(self.cookies, file)

    def _setInventory(self):
        url = 'https://cs.money/3.0/load_user_inventory/730?limit=60&noCache=true&offset=0&order=desc&sort=price&withStack=true'

        if 'expired' in self.cookies:
            self._loadCookies()

            if 'expired' in self.cookies:  # try to load new cookies
                self.inventory = {'expired': True}
                return

        response = self.session.get(url).json()
        print(response)

        if response.get('error') == 4:
            self.logger.warning('steam error')
            self.inventory = {}
            return

        if response.get('error') == 6:
            self.logger.critical('csm cookies expired')
            self._setCookiesExpired()
            self.inventory = {'expired': True}
            return

        inventory = response['items']
        hashDictInventory = {}

        for item in inventory:
            itemHash = getHash(item['fullName'], item.get('float'))
            hashDictInventory[itemHash] = item

        self.inventory = hashDictInventory

    def getHashDictInv(self):
        res = {}

        if 'expired' in self.inventory:
            return self.inventory

        for itemHash, data in self.inventory.items():
            default_price = data['defaultPrice']

            if default_price == 0:
                continue

            price = data['price']
            res[itemHash] = price / default_price - 1

        return res

    @staticmethod
    def loadOverstockItems():
        for i in range(5):
            try:
                resp = requests.get('https://cs.money/list_overstock?appId=730').json()
            except Exception as e:
                print(f'could not get list of overstock items - {e}')

                if i == 4:
                    return None

        res = []

        for entry in resp:
            res.append(entry['market_hash_name'])

        return res
