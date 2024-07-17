import json
import os
import pickle
import random
import time

from loggingUtils import loggingConfig
from dataLayer.InvenoryRepository import InventoryRepository
from models import Account, Deal, Order
from steam.LoginExecutor import LoginExecutor
from tools.itemTools import getHashFromInspect, getHash


class itemBuyer(loggingConfig.AbstractLoggingClass):
    def __init__(self, accountName):
        self.account = Account(accountName)
        self.logger = loggingConfig.AccountAdapter(self.logger, extra=self.account.getDict())
        self.last_buys = {}

    def buy_item(self,
                 deal: Deal):  # в случае покупки по автопокупке сюда должен передаваться оверпей по ордеру чтобы проверить настоящую цену, в случае покупки по кнопке похуй тк так и так цена правильная
        self.logger.info(
            f'buying {deal.itemName} with {deal.itemFloat} float and {deal.pattern} pattern for {deal.price}, reason {deal.buyingReason}')


        item_name = deal.itemName
        
        # 2 good for same item are unlikely to pop up in the span of 10 minutes,
        # such event is probably an indication of the profit estimation system going bust
        if item_name in self.last_buys and time.time() - self.last_buys[item_name] < 10 * 60:
            self.logger.critical(f'attempted to buy {item_name} for than once in 10 minutes')
            self.last_buys[item_name] = time.time()
            return

        self.last_buys[item_name] = time.time()

        le = LoginExecutor(self.account.username)
        steamSession = le.getAccountSession()

        data = {
            "sessionid": steamSession.cookies.get_dict()['sessionid'],
            "currency": 3,
            "subtotal": deal.price - deal.fee,
            "fee": deal.fee,
            "total": deal.price,
            "quantity": 1
        }

        headers = {'Referer': f"https://steamcommunity.com/market/listings/730/{deal.itemName}".encode('utf-8')}
        response = None

        try:
            response = steamSession.post(f'https://steamcommunity.com/market/buylisting/{deal.mValue}', data,
                                         headers=headers)
            if response.status_code != 200:
                raise Exception(f"http error {response.status_code} while attempting purchase")

            response = response.json()
        except Exception as e:
            self.logger.info(f'http error {e} while attempting purchase')

        if deal.buyingReason == 'patternVip':
            self.logger.critical(f'tried to buy a vip pattern item - {deal.itemName}, {deal.pattern}')

        if "wallet_info" in response:
            if deal.itemName is None or deal.itemFloat is None:
                if deal.link is not None:
                    itemHash = getHashFromInspect(deal.link)
                else:
                    self.logger.critical(f'item will be left untracked in db - '
                                         f'not enough info to create hash. Available info: {deal.__dict__}')
                    return
            else:
                itemHash = getHash(deal.itemName, deal.itemFloat)

            self.logger.info('success')

            if deal.buyingReason == 'profit_vip':
                self.logger.critical(f'bought vip pattern item - {deal.itemName}, {deal.pattern}')

            item_to_add = InventoryRepository.Record(
                    item_type=deal.buyingReason,
                    item_name=deal.itemName,
                    account_to_transfer=self.account.username,
                    current_account=self.account.username,
                    item_id=itemHash
                )

            if deal.buyingReason not in Order.orderTypes:
                # assuming buying reason is a marketplace
                with open(f'data/{deal.buyingReason}Accounts.json', 'r') as file:
                    accounts = json.load(file)

                item_to_add.account_to_transfer = random.choice(accounts)

            InventoryRepository().blocking().insert(item_to_add)


    def checkForDeals(self):
        dirPath = os.path.dirname(os.path.abspath(__file__)) + f'/../data/deals/{self.account.username}'

        while True:
            time.sleep(0.01)
            deals = os.listdir(path=dirPath)

            for dealPath in deals:
                self.dealHandler(dirPath + '/' + dealPath)

    def dealHandler(self, dealPath):
        try:
            with open(dealPath, 'rb') as file:
                deal = pickle.load(file)

            os.remove(dealPath)
        except Exception as e:
            print(e)
            return

        self.buy_item(deal)
