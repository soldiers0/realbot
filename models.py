import json
import random
import time

from steampy.models import Asset
from steampy.models import GameOptions


class Account:
    def __init__(self, name, accountsFolder='accounts/', csgomarketAccount=False):
        pathToFiles = accountsFolder + name + '/'

        with open(f'{pathToFiles}steamUsername.txt', 'r') as file:
            self.username = file.read()

        with open(f'{pathToFiles}steamPassword.txt', 'r') as file:
            self.password = file.read()

        with open(f'{pathToFiles}steamKey.txt', 'r') as file:
            self.steamKey = file.read()

        if csgomarketAccount:
            with open(f'{pathToFiles}key.txt', 'r') as file:
                self.csgomarketKey = file.read()

        self.proxy = pathToFiles + 'proxy.json'
        self.steamGuard = pathToFiles + 'Steamguard.txt'
        with open(self.steamGuard, 'r') as file:
            self.steam_id = str(json.load(file).get('steamid'))

    def getDict(self):
        return {
            'steamUsername': self.username,
            'steamPassword': self.password,
            'steamKey': self.steamKey,
            'proxy': self.proxy,
            'steamGuard': self.steamGuard
        }


class Deal:
    def __init__(self, itemName=None, mValue=None, pattern=None, price=None, fee=None, link=None, itemFloat=None,
                 overpay=None, stickers=None, buyingReason='float'):
        self.itemName = itemName
        self.mValue = mValue
        self.pattern = pattern
        self.price = price
        self.fee = fee
        self.link = link
        self.itemFloat = itemFloat
        self.overpay = overpay
        self.id = random.randint(1, 1000000000)
        self.stickers = stickers
        self.buyingReason = buyingReason

    def __repr__(self):
        return f'{self.itemName} for {self.price} with fee {self.fee}. float - {self.itemFloat}, pattern - {self.pattern}'

    def isSuitableForOrder(self, order):
        if not (self.pattern in order.patterns) and order.patterns != []:
            # print('wrong pattern')
            return False

        if not order.minFloat < self.itemFloat < order.maxFloat:
            # print('wrong float')
            return False

        if self.overpay > order.maxOverpay:
            # print('wrong overpay')
            return False

        if self.stickers == "":
            dealStickers = []
        else:
            dealStickers = self.stickers.split(';')[::-1]  # там в конце от ; будет просто пустая строка.

        if order.stickers == "" or order.stickers == None:
            return True
        else:
            orderStickers = order.stickers.split(';')[::-1]

        foundSticker = False

        for sticker in dealStickers:
            if sticker in orderStickers:
                foundSticker = True

        return foundSticker


class SteampyItem(Asset):
    def __init__(self, asset_id: str):
        super().__init__(asset_id, GameOptions('730', '2'))


class Order:
    orderTypes = {'float', 'pattern', 'patternVip', 'profit', 'profit_vip'}

    def __init__(self, *, telegramId: int = None, itemName: str = None, minFloat: float = None, maxFloat: float = None,
                 patterns: list[str] = None, stickers: str, maxOverpay: int = None, profit_per_day: int = 0,
                 orderType='float'):
        self.telegramId = telegramId
        self.itemName = itemName
        self.minFloat = minFloat
        self.maxFloat = maxFloat
        self.patterns = patterns
        self.maxOverpay = maxOverpay
        self.stickers = stickers
        self.patternsString = str(self.patterns)[1:-1:]
        self.patternsString = self.patternsString.replace(',', '')
        self.orderType = orderType
        self.profit_per_day = profit_per_day


class Page:
    def __init__(self, name, pageNumber):
        self.name = name
        self.pageNumber = pageNumber
        self.tries = 0


class Proxy:
    def __init__(self, url):
        self.url = url
        self.last_requests = {}


class AbstractAnalyzer:
    sellFee = None
    withdrawFee = 0.99  # по дефолту если на площадке нет возможности вывести
    marketplaceName: str = None

    class SellingInfoNotSpecified(Exception):
        pass

    class WithdrawInfoNotSpecified(Exception):
        pass

    class NoPriceInfoError(Exception):
        def __init__(self, itemName, marketplaceName):
            super().__init__(f'no price info for {itemName} - {marketplaceName}')

    def getBuyPrice(self, itemName: str, **kwargs):
        raise NotImplementedError

    def getSellPrice(self, itemName: str, **kwargs):
        raise NotImplementedError

    def getDailyTradeVolume(self, itemName: str, **kwargs):
        raise NotImplementedError

    def buyCheapestItem(self, itemName: str, reasonForBuying: str, reference_price: int = None):
        raise NotImplementedError


if __name__ == '__main__':
    NameIdData()