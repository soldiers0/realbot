import json
import pickle
import time

from bs4 import BeautifulSoup

from loggingUtils import loggingConfig
import requests
from models import Account, SteampyItem
from steampy.client import SteamClient
from steampy.market import SteamMarket
from steampy.models import GameOptions
from tools.itemTools import getFloat, getHash


class AccountHandler(loggingConfig.AbstractLoggingClass):
    def __init__(self, accountName):
        self.accountName = accountName
        self.account = Account(accountName)
        self.logger = loggingConfig.AccountAdapter(self.logger, extra=self.account.getDict())
        self.performLogin()
        self.csgo = GameOptions('730', '2')
        self.client.was_login_executed = True

    def get_session(self) -> requests.session:
        with open(f'data/loggedSessions/{self.accountName}.pkl', 'rb') as file:
            session = pickle.load(file)

        return session

    def performLogin(self):
        self.client = SteamClient(self.account.steamKey)

        session = self.get_session()

        self.client._session = session

        self.client.username = self.accountName
        self.client._password = self.account.password
        self.client._api_key = self.account.steamKey

        with open(f'accounts/{self.accountName}/Steamguard.txt') as file:
            self.client.steam_guard = json.load(file)

        self.client.market = SteamMarket(self.client._session)
        self.client.market._set_login_executed(self.client.steam_guard, session.cookies.get_dict()['sessionid'])
        self.consecutiveFailures = 0

    def steamRequestWrapper(func):
        def wrapper(*args):
            self = args[0]
            with open(f'data/loggedSessions/{self.accountName}.pkl', 'rb') as file:
                session = pickle.load(file)

            self.client._session = session
            self.client.market._session = session

            sleepTime = min(100, 10 ** (self.consecutiveFailures - 1))

            if sleepTime > 1:
                self.logger.info(f'sleeping for {sleepTime} seconds, because of previous failures')

            time.sleep(sleepTime)

            try:
                res = func(*args)
                self.consecutiveFailures = 0
                return res
            except Exception as e:
                self.logger.warning(f'error while executing {func.__name__} - {e}')

            self.consecutiveFailures += 1

        return wrapper

    @steamRequestWrapper
    def _getInventory(self):
        self.logger.info('getting inventory')
        return self.client.get_my_inventory(self.csgo)

    @steamRequestWrapper
    def getAllListings(self):
        self.logger.info('getting listings')
        return self.client.market.get_my_market_listings().get('sell_listings')

    @steamRequestWrapper
    def cancelListing(self, a):
        self.logger.info('cancelling listings')
        self.client.market.cancel_sell_order(a)

    @steamRequestWrapper
    def acceptTrade(self, tradeId: str) -> bool:
        self.logger.info('accepting trade')
        return bool(self.client.accept_trade_offer(tradeId))

    @steamRequestWrapper
    def performConfirmation(self, confirmationId):
        self.logger.info('confirming trade')
        return self.client._confirm_transaction(confirmationId)

    @steamRequestWrapper
    def sellItem(self, assetId, price):
        """price in rubles"""
        self.logger.info('selling item')
        return self.client.market.create_sell_order(assetId, self.csgo, price * 87)
        # multiplying by 87 because function takes in amount money received not paid

    @steamRequestWrapper
    def transferItems(self, items_to_transfer: list[SteampyItem] | SteampyItem | str | list[str], steamId: str) -> str | None:
        self.logger.info('transferring items')
        if type(items_to_transfer) != type(list):
            items_to_transfer = [items_to_transfer]

        for i in range(len(items_to_transfer)):
            if type(items_to_transfer[i]) == str:
                items_to_transfer[i] = SteampyItem(items_to_transfer[i])

        return self.client.make_offer(items_to_transfer, [], steamId).get('tradeofferid')

    @steamRequestWrapper
    def transferItemsWithUrl(self, items_to_transfer: list[SteampyItem] | SteampyItem | list[str] | str, partnerID: str, token: str) -> str | None:
        url = f'https://steamcommunity.com/tradeoffer/new/?partner={partnerID}&token={token}'
        self.logger.info('transferring items')
        if type(items_to_transfer) != list:
            items_to_transfer = [items_to_transfer]

        for i in range(len(items_to_transfer)):
            if type(items_to_transfer[i]) == str:
                items_to_transfer[i] = SteampyItem(items_to_transfer[i])

        return self.client.make_offer_with_url(items_to_transfer, [], url).get('tradeofferid')

    def getTradesToConfirm(self):
        res = []
        tradeData = self.requestTrades()

        for tradeOffer in tradeData['response']['trade_offers_sent']:
            if tradeOffer['trade_offer_state'] == 9:  # ждёт подтверждения
                res.append(tradeOffer['tradeofferid'])

        return res

    def confirmAllTrades(self):
        self.logger.debug('confirming all trades')
        trades = self.getTradesToConfirm()

        for trade in trades:
            self.performConfirmation(trade)

    def requestTrades(self):
        try:
            response = requests.get(
                f'http://api.steampowered.com/IEconService/GetTradeOffers/v1/?key={self.account.steamKey}&get_sent_offers=true')
            return response.json()
        except Exception as e:
            self.logger.warning(f'could not make GetTradeOffers request - {e} account: {self.accountName}')
            return {}

    def _formatItemsInfo(self, fullInfo, onlyTradable=False, onlySkins=False, marketHistory=False) -> dict:
        res = {}

        for entry in fullInfo:
            currentlyOnMarket = False
            tradable = True
            itemInfo = fullInfo[entry]

            if 'need_confirmation' in itemInfo and itemInfo[
                'need_confirmation']:  # предмет уже был выставлен но по той или иной причине ждёт конфирмейшена
                continue

            elif 'description' in itemInfo:  # листинг на площадке
                currentlyOnMarket = True
                desc = itemInfo['description']

                if not desc['tradable']:
                    tradable = False

                a = desc['id']
                link = desc['actions'][0]['link']
                ms = entry

                name = desc['market_hash_name']
            else:  # инвентарь
                a = entry

                if onlySkins and 'actions' not in itemInfo:  # контейнер
                    continue

                if not itemInfo['tradable']:
                    tradable = False

                link = itemInfo['actions'][0]['link']
                ms = self.account.steam_id

                name = itemInfo['market_hash_name']

            if onlyTradable and not tradable:
                continue

            qualities = ['Battle-Scarred', 'Well-Worn', 'Field-Tested', 'Minimal Wear', 'Factory New']
            isSkin = not onlySkins  # если онлискинс фолс, то это сразу тру и проверки не происходит

            for qualitiy in qualities:
                if qualitiy in name:
                    isSkin = True

            if not isSkin:
                continue

            d = link[link.find('D') + 1::]
            float_val = getFloat(ms, a, d, fromInventory=not currentlyOnMarket)
            item_hash = getHash(name, float_val)

            res[item_hash] = {
                'name': name,
                'float': float_val,
                'a': a,
                'ms': ms,
                'd': d,
                'on_market': currentlyOnMarket,
                'tradable': tradable
            }

        return res

    @staticmethod
    def _format_market_history(assets: dict, html: str):
        """
        only returns listings with inspect link available
        """
        action_indicators = {
            'Buyer': 'sell',
            'Seller': 'buy',
            'Listing canceled': 'cancel',
            'Listing created': 'create'
        }

        soup = BeautifulSoup(html)
        html_actions = soup.findAll('div', {'class': 'market_listing_right_cell market_listing_whoactedwith'})
        actions = [action_indicators[[key for key in action_indicators.keys() if key in html_action.text][0]]
                   for html_action in html_actions[1:]]
        result = []
        it = -1
        for entry, data in assets['730']['2'].items():
            it += 1

            if 'market_actions' not in data:
                continue

            link = data['market_actions'][0]['link']
            link = link.replace('%assetid%', entry)
            result.append({
                'hash': getHashFromInspect(link),
                'action': actions[it]
            })

        return result

    @steamRequestWrapper
    def get_market_history(self, last_recorded_total: int) -> tuple[list[dict], int] | tuple[list, None]:
        """
        last_recorded_total refers to amount of total market operations at the time of last request, only new ones
        will be fetched.
        returns (result, current_total)
        """
        current_total = self.client.market.get_trade_history(0, 10)[0]

        if current_total is None:
            return [], None

        records_to_fetch = current_total - last_recorded_total

        # just some value to fetch the current total
        if last_recorded_total == -1:
            records_to_fetch = 0

        if records_to_fetch == 0:
            return [], current_total

        result = []

        for i in range(records_to_fetch // 100 + 1):
            _, assets, html = self.client.market.get_trade_history(i * 100, min(100, records_to_fetch - i * 100))
            result.extend(self._format_market_history(assets, html))

        return result, current_total

    def get_inventory(self, onlyTradable=False, onlySkins=False):
        _inventory = self._getInventory()

        if _inventory is None:
            return {}

        return self._formatItemsInfo(_inventory, onlyTradable=onlyTradable, onlySkins=onlySkins)

    def cancelAllListings(self):
        itemsInfo = self._formatItemsInfo(self.getAllListings())

        for item in itemsInfo:
            name = itemsInfo[item]['name']
            ms = itemsInfo[item]['ms']

            self.cancelListing(ms)