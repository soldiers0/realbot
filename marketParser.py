from models import AbstractAnalyzer

from loggingUtils import loggingConfig
from config.cfg import config

import random
import threading
import time

from steam.Analyzers import PriceChartSteamAnalyzer


class MarketParser(loggingConfig.AbstractLoggingClass):
    def __init__(self, skinsToParse):
        self.skinsToParse = skinsToParse

    def startParsingThreads(self, numberOfThreads=5):
        random.shuffle(self.skinsToParse)
        skins = self.skinsToParse
        thread_item_lists = [[] for _ in range(numberOfThreads)]
        self.threadFinishedFlags = [False for _ in range(numberOfThreads)]

        for i, skin in enumerate(skins):
            thread_item_lists[i % numberOfThreads].append(skin)

        for i in range(numberOfThreads):
            thread = threading.Thread(target=self.parsingThread, args=(thread_item_lists[i], i))
            thread.start()

        while False in self.threadFinishedFlags:
            time.sleep(60)

    def parsingThread(self, skins: list[str], i: int):

        for itemName in skins:
            try:
                self.analyzeItem(itemName)
            except Exception as e:
                self.logger.exception(e)
            time.sleep(5)

        self.threadFinishedFlags[i] = True

    def analyzeItem(self, item):
        raise NotImplementedError


class WithdrawalParser(MarketParser):
    def __init__(self, skinsToParse: list[str], buyingAnalyzer: AbstractAnalyzer, platformsToSell: list[AbstractAnalyzer]):
        super().__init__(skinsToParse)

        self.buyingAnalyzer: AbstractAnalyzer = buyingAnalyzer
        self.platformsToSell: list[AbstractAnalyzer] = platformsToSell
        self.cfg = config().this()

    def analyzeItem(self, itemName: str):
        try:
            buyingPrice = self.buyingAnalyzer.getBuyPrice(itemName)
        except self.buyingAnalyzer.NoPriceInfoError as e:
            self.logger.warning(e)
            return

        for sellingAnalyzer in self.platformsToSell:
            try:
                sellingPrice = sellingAnalyzer.getSellPrice(itemName)
                salesPerMonth = sellingAnalyzer.getDailyTradeVolume(itemName) * 30
            except sellingAnalyzer.NoPriceInfoError:
                self.logger.info(f'no price info for {itemName}')
                return

            if None in (buyingPrice, sellingPrice, salesPerMonth):
                return

            self.logger.debug(f"{itemName}, {buyingPrice}, {sellingPrice}")

            sellPriceAfterFee = sellingPrice * (1 - sellingAnalyzer.sellFee)
            withdrawableMoney = sellPriceAfterFee * (1 - sellingAnalyzer.withdrawFee)

            withdrawToBuyRatio = withdrawableMoney / buyingPrice

            from dataLayer.InvenoryRepository import InventoryRepository

            condition = InventoryRepository.Record(
                item_name=itemName,
                item_type=sellingAnalyzer.marketplaceName
            )

            inv_items_of_type = InventoryRepository().blocking().select(condition)

            flag = True
            flag &= withdrawToBuyRatio >= self.cfg['min_withdrawal_ratio']
            flag &= salesPerMonth >= self.cfg['min_monthly_volume']
            flag &= self.cfg['min_price'] <= buyingPrice <= self.cfg['max_price']
            flag &= len(inv_items_of_type) < self.cfg['max_inv_items']

            if flag:
                self.logger.critical(f'buying {itemName} for {buyingPrice} with expected withdrawal price of {buyingPrice * withdrawToBuyRatio}')
                self.buyingAnalyzer.buyCheapestItem(itemName, sellingAnalyzer.marketplaceName,
                                                    reference_price=buyingPrice)


class AccountSteamParser(loggingConfig.AbstractLoggingClass):
    """
    Analyzes item prices and trade volume by fetching price chart with logged sessions
    Saves data to market_info table
    """

    def run(self):
        from dataLayer.CsmFloatOverpayRecords import CsmFloatOverpayRecords
        from dataLayer.marketInfo import MarketInfoRepository
        from requestHandler import TooManyRequests
        items_with_overpay = list(CsmFloatOverpayRecords(debug=True).blocking().get_all_records().keys())
        active_accounts: list[str] = config()['active_accounts']

        time_in_jail = 60 * 10  # 10 minutes
        account_jail: dict[str, float] = {}

        while True:
            items = iter(items_with_overpay)
            get_next_item = True
            item_name = None

            while True:
                try:
                    accounts_to_free = []

                    for account_name, in_jail_until in account_jail.items():
                        if time.time() > in_jail_until:
                            accounts_to_free.append(account_name)

                    for account_name in accounts_to_free:
                        active_accounts.append(account_name)
                        account_jail.pop(account_name)

                    if not active_accounts:
                        time.sleep(10)
                        continue

                    account_name = random.choice(active_accounts)

                    # get_next_item can be false if previous iteration was unsuccessful because of TooManyRequests
                    if get_next_item:
                        item_name = next(items, None)

                    # all items were parsed
                    if item_name is None:
                        break

                    try:
                        item_price, daily_volume = PriceChartSteamAnalyzer().getItemInfo(
                            item_name, account_name=account_name
                        )
                    except TooManyRequests:
                        self.logger.info(f"too many requests - {account_name}")
                        account_jail[account_name] = time.time() + time_in_jail
                        active_accounts.remove(account_name)
                        get_next_item = False
                        continue

                    self.logger.info(f"{item_name} - price: {item_price}, daily_volume: {daily_volume}")

                    record = MarketInfoRepository.Record(
                        item_name=item_name, avg_sell_price=item_price, daily_volume=daily_volume
                    )

                    MarketInfoRepository().blocking().update_item_data(record)
                    get_next_item = True
                    time.sleep(10)
                except Exception as e:
                    self.logger.exception(e)



class ProxySteamParser(MarketParser):
    """
    Analyzes item prices and trade volume by fetching price chart with logged sessions
    Saves data to market_info table
    """

    def analyzeItem(self, item):
        from dataLayer.marketInfo import MarketInfoRepository
        item_price, daily_volume = PriceChartSteamAnalyzer().getItemInfo(item, use_proxy=True)
        record = MarketInfoRepository.Record(item_name=item, avg_sell_price=item_price, daily_volume=daily_volume)
        self.logger.info(f"paresed item: {record.item_name} {record.avg_sell_price} {record.daily_volume}")
        MarketInfoRepository().blocking().update_item_data(record)

