import asyncio
import datetime
import pickle
import random

import config.cfg
from loggingUtils import loggingConfig

from steam.steam_requests import *
from models import AbstractAnalyzer, Deal
from dataLayer.ItemNameIdRepository import ItemNameIdRepository
from config.cfg import config


class SimpleSteamAnalyzer(AbstractAnalyzer, loggingConfig.AbstractLoggingClass):
    marketplaceName = 'steam'

    def __init__(self):
        with open('data/buyingAccounts.json', 'r') as file:
            self.buyingAccounts = json.load(file)
        self.steamPriceOffset = config()['Analyzers']['steamPriceOffset']


    def priceRequest(func):
        def wrapper(*args, **kwargs):
            itemName = args[1]

            try:
                query = ItemNameIdRepository.Record(name=itemName)
                record: ItemNameIdRepository.Record = ItemNameIdRepository().blocking().select(query)[0]
                itemNameId = record.item_name_id
            except IndexError:
                ''' 
                if IndexError is raised than itemNameId is not in the db which 
                means we have to try to parse it once more
                '''
                itemNameId = asyncio.run(getItemNameId(itemName))

                if itemNameId is not None:
                    ItemNameIdRepository().blocking().add_record(itemName, itemNameId)

            args = list(args)
            args[1] = itemNameId
            return func(*args, **kwargs)

        return wrapper

    def getSellPrice(self, itemName: str, max_offset_correction=0.8, min_volume=30):
        """
        max_offset_correction stands for the amount of overprice we can slash depending on the volume i.e.
        if offset is 1.10, with default value we will decrease it by up to 0.05.
        min_volume is threshold after which offset is not changed
        """
        try:
            current_price = self.getBuyPrice(itemName)
            volume = self.getDailyTradeVolume(itemName)

            if volume is None:
                volume = 0

            if volume > 10:
                return int(current_price * self.steamPriceOffset)

            steam_overprice = self.steamPriceOffset - 1

            correction = steam_overprice * max_offset_correction * volume / min_volume

            volume_correction = steam_overprice * max_offset_correction - correction

            return int(current_price * (self.steamPriceOffset - volume_correction))
        except Exception as e:
            self.logger.warning(f'could not get item sell price - {e}')

    @priceRequest
    def getBuyPrice(self, itemName):
        try:
            return int(int(asyncio.run(getLowestSellOrder(itemName))) / 100)
        except Exception as e:
            self.logger.error(f'could not get item buy price for {itemName}')

    def getDailyTradeVolume(self, itemName: str, proxy=None):
        try:
            data = asyncio.run(getItemSellInfo(itemName))
            if data is None or 'volume' not in data:
                return None
            return int(data.get('volume'))
        except Exception as e:
            self.logger.error(f'could not get {itemName} sales volume - {e}')

    def buyCheapestItem(self, itemName: str, buyingReason: str, reference_price: float = None):
        account = random.choice(config.cfg.config()['mainParser']['buying_accounts'])
        cheapest_listing = asyncio.run(get_cheapest_item(itemName, account_name=account))

        if cheapest_listing is None:
            self.logger.warning(f'could not get listings for - {itemName}')
            return

        m_value = cheapest_listing['m']
        price = cheapest_listing['price']
        fee = cheapest_listing['fee']
        link = cheapest_listing['link']
        deal = Deal(mValue=m_value, price=price, fee=fee, buyingReason=buyingReason, link=link, itemName=itemName)

        price_diff = price / 100 - reference_price

        if price_diff / reference_price < 0.01:
            # either actual price is lower than expected or the difference is less than 1%
            for accountName in self.buyingAccounts:
                with open(f"data/deals/{accountName}/{deal.mValue}.pkl", 'wb') as file:
                    pickle.dump(deal, file, pickle.HIGHEST_PROTOCOL)


class PriceChartSteamAnalyzer(SimpleSteamAnalyzer):
    import pandas as pd

    @staticmethod
    def _get_quantile_price(data: pd.DataFrame, quantile, period_days=7):
        assert 0 < quantile < 1

        if data is None:
            return None

        data: pd.DataFrame

        minimum_data_points = 5
        days = period_days

        # if there were less than 5 deals during period_days add a day
        # to the timeframe while the aforementioned condition is not satisfied
        while True:
            time_frame_data = data[data.index > datetime.datetime.now() - pd.Timedelta(days=days)]

            if len(time_frame_data) >= minimum_data_points:
                data = time_frame_data
                break
            else:
                days += 1

        sell_price = data.quantile(quantile)['Price']
        return sell_price

    @staticmethod
    def _get_data(item_name, account_name=None, use_proxy=False):
        return asyncio.run(get_sell_price_history(item_name, account_name=account_name, use_proxy=use_proxy))

    @staticmethod
    def _get_daily_volume(data: pd.DataFrame, period_days=14) -> float:
        return len(data[data.index > datetime.datetime.now() - pd.Timedelta(days=period_days)]) / period_days

    def getSellPrice(self, item_name: str, account_name: str = None, **kwargs):
        """

        returns 90 percentile over last 2 weeks

        """
        return self._get_quantile_price(self._get_data(item_name, account_name=account_name), 0.9)

    def getItemInfo(self, item_name: str, account_name: str = None, period_days=14, use_proxy = False) -> tuple[float, float]:
        """
        returns (median sell price, daily volume)
        """

        data = self._get_data(item_name, account_name=account_name, use_proxy=use_proxy)
        median_price = self._get_quantile_price(data, 0.5, period_days=period_days)
        daily_volume = self._get_daily_volume(data, period_days=period_days)
        return median_price, daily_volume
