import json

import requests
import time
from models import Account
from models import SteampyItem
import threading

from inventoryHandler import InventoryHandler
from models import AbstractAnalyzer
from loggingUtils.loggingConfig import AbstractLoggingClass

class RequestError(Exception):
    pass


class SimplePlznomarketAnalyzer(AbstractAnalyzer):
    sellFee = 0.05
    withdrawFee = 0.05
    marketplaceName = 'plznomarket'

    def __init__(self, priceUpdateInterval=120):
        self.pricesData = None

        while self.pricesData is None:
            self.updatePriceList()

        self.lastPriceUpdate = time.time()
        self.priceUpdateInterval = priceUpdateInterval

    def updatePriceList(self):
        try:
            items = requests.get('https://market.csgo.com/api/v2/prices/RUB.json').json()['items']
        except Exception as e:
            print(f'could not get csgomarket prices list - {e}')
            return None

        prices = {}

        for item in items:
            prices[item['market_hash_name']] = {
                'price': int(float(item['price']) * 100),
                'volume': int(item['volume'])
            }

        self.pricesData = prices
        self.lastPriceUpdate = time.time()

    def itemInfoRequest(func):
        def wrapper(*args, **kwargs):
            self = args[0]
            itemName = args[1]

            if time.time() - self.lastPriceUpdate > self.priceUpdateInterval:
                self.updatePriceList()

            if itemName not in self.pricesData:
                raise self.NoPriceInfoError(itemName, self.marketplaceName)

            return func(*args)

        return wrapper

    #цены в копейках
    @itemInfoRequest
    def getSellPrice(self, itemName: str) -> int:
        return (self.pricesData[itemName]['price'] - 50) // 100  #предположим что итоговая цена продажи будет на 50 коп. меньше

    @itemInfoRequest
    def getDailyTradeVolume(self, itemName: str) -> int:
        return self.pricesData[itemName]['volume'] // 30

    @itemInfoRequest
    def getBuyPrice(self, itemName: str) -> int:
        return self.pricesData[itemName]['price']


class simpleSeller(AbstractLoggingClass):  #просто перебивает цены конкурентов на копейку
    #TODO add logging
    def __init__(self, accountName: str, analyzer: AbstractAnalyzer):
        self.account = Account(accountName, csgomarketAccount=True)
        self.ih = InventoryHandler(accountName)
        self.analyzer = analyzer

    def makeRequest(self, endpoint, tries=3, **kwargs):
        key = self.account.csgomarketKey
        csgoMarketUrl = 'https://market.csgo.com/api/v2'

        kwargs['key'] = key
        kwargsString = ''

        for keyWord, value in kwargs.items():
            kwargsString += f'{keyWord}={value}&'

        for i in range(tries):
            try:
                res = requests.get(f'{csgoMarketUrl}/{endpoint}?{kwargsString[:-1]}')

                if res is not None and res.json().get('success'):
                    return res.json()

                #нечего передавать, там success false просто в этом случае
                if endpoint == 'trade-request-give-p2p-all' and res is not None and res.json().get('error') == 'nothing':
                    return {'offers': []}

                if res is not None:
                    self.logger.error(f'{res.json()}, {endpoint}, {self.account.username}')

                time.sleep(5)

            except Exception:
                time.sleep(5)

        raise RequestError()

    def setNewPrice(self, itemId, price):
        self.makeRequest('set-price', item_id=itemId, price=price, cur='RUB')

    def sellItem(self, itemId, price):
        self.makeRequest('add-to-sale', id=itemId, price=price, cur='RUB')

    def getTransferInfo(self):
        data = self.makeRequest('trade-request-give-p2p-all')
        res = []

        for offer in data['offers']:
            for item in offer['items']:
                res.append((SteampyItem(str(item['assetid'])), offer['partner'], offer['token']))

        return res

    def getItemsOnSale(self):
        try:
            itemsOnSale = []
            res = self.makeRequest('items')
            items = res['items']

            if items is None:
                return  []

            for item in items:
                if item['status'] == '1':
                    itemsOnSale.append({
                        'internalId': item['item_id'],
                        'price': int(float(item['price']) * 100),
                        'name': item['market_hash_name']
                    })

            return itemsOnSale

        except RequestError:
            return []

    def getInventory(self):
        try:
            inventory = []
            res = self.makeRequest('my-inventory')
            items = res['items']

            for item in items:
                inventory.append({
                    'steamId': item['id'],
                    'name': item['market_hash_name']
                })

            return inventory
        except RequestError:
            return []

    def updateSellingItems(self):
        try:
            inventory = self.getInventory()

            for item in inventory:
                try:
                    self.sellItem(item['steamId'], self.analyzer.getBuyPrice(item['name']) - 1)
                except SimplePlznomarketAnalyzer.NoPriceInfoError:
                    continue

            itemsOnSale = self.getItemsOnSale()

            for item in itemsOnSale:
                try:
                    buyPrice = self.analyzer.getBuyPrice(item['name'])
                except SimplePlznomarketAnalyzer.NoPriceInfoError:
                    continue

                if item['price'] > buyPrice:
                    self.setNewPrice(item['internalId'], buyPrice - 1)

        except RequestError:
            pass

    def transferItems(self):
        try:
            transferInfo = self.getTransferInfo()

            for itemToTransfer, partnerId, token in transferInfo:
                self.ih.transferItemsWithUrl([itemToTransfer], partnerId, token)

            if transferInfo:
                self.makeRequest('update-inventory')
        except RequestError:
            pass

    def pinging(self):
        while True:
            try:
                self.makeRequest('ping')
            except RequestError:
                pass

            time.sleep(60)

    def updatingInventory(self):
        while True:
            try:
                self.makeRequest('update-inventory')
            except RequestError:
                pass

            time.sleep(300)

    def selling(self):
        while True:
            self.updateSellingItems()
            time.sleep(100)

    def transferingItems(self):
        while True:
            self.transferItems()
            time.sleep(100)

    def startSelling(self):
        pingingThread = threading.Thread(target=self.pinging)
        sellingThread = threading.Thread(target=self.selling)
        transferingThread = threading.Thread(target=self.transferingItems)
        updateInventoryThread = threading.Thread(target=self.updatingInventory)

        pingingThread.start()
        sellingThread.start()
        updateInventoryThread.start()
        transferingThread.start()


if __name__ == '__main__':
    with open('data/plznomarketAccounts.json', 'r') as file:
        accounts = json.load(file)

    threads = \
        [threading.Thread(target=simpleSeller(account, SimplePlznomarketAnalyzer()).startSelling()) for account in accounts]

    for thread in threads:
        thread.start()
