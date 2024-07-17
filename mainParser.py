# -*- coding: utf-8 -*-
import json
import asyncio
import pickle

import dataLayer.marketInfo
from loggingUtils import loggingConfig

from fileWriter import FileWriter
from fileWriter import getJsonedCache, unJsonCache
from csgofloat import get_float_pattern_stickers
from steam.steam_requests import getPageListingsInfo
from csmoney.csmOverpayAnalyzers import *
from dataLayer.InvenoryRepository import InventoryRepository
from dataLayer.ItemsInfoRepository import ItemsInfoRepository

from config.cfg import config


def isBroken(data):
    for key in ['itemNameId', 'avgSellPrice', 'pagesToParse', 'lastUpdated']:
        if key not in data or data[key] is None:
            return True

    return False


class PatternScrapper(loggingConfig.AbstractLoggingClass):
    def __init__(self):
        self.cfg = config().this()
        self.fileWriter = FileWriter(
            backUpList=['itemCache.json', 'autoItemCache.json'])
        #  items that are actively parsed and can be bought
        self.item_list_profit = []

        #  items that are analyzed so that next time loadItemlist.expected_profit there will be price info
        self.items_to_add_profit = []

        #  maximum price of an item to be sold with automatic price estimation
        self.max_auto_sell_price = config()['max_auto_price']
        self.itemData: dict[str, dataLayer.marketInfo.MarketInfoRepository.Record] = {}

        with open('data/autoItemCache.json', 'r') as file:
            self.itemCache = json.load(file)

        unJsonCache(self.itemCache)

        with open('data/buyingAccounts.json', 'r') as file:
            self.buyingAccounts = json.load(file)

        self.absentItems = {}

    async def main(self):
        while True:
            try:
                #  load item list
                await self.loadItemList()

                # these are reset since otherwise, because there are no active pollers, they will be duplicated
                self.items_to_add_profit = []

                tasks = []

                for item in self.item_list_profit:
                    tasks.append(asyncio.ensure_future(self.itemPoller(item)))

                tasks.append(asyncio.ensure_future(self.dbPoller()))
                tasks.append(asyncio.ensure_future(self.filesPoller()))

                await asyncio.gather(*tasks)
            except Exception as e:
                self.logger.exception(e)
                raise e

    async def itemPoller(self, item, RECURSION_DEPTH=0, START_DELAY=0,):
        await asyncio.sleep(START_DELAY)
        self.logger.info(f'added {item}')

        skip_csgo_float_request = True
        while True:
            # item is longer in active pool or has changed its pool
            if item not in self.item_list_profit:
                self.logger.info(f'removed {item}')
                return

            # there are new items in current pool to add
            if self.items_to_add_profit and RECURSION_DEPTH < 5:
                items_to_add = self.items_to_add_profit
                self.items_to_add_profit = []

                # only profit items are force analyzed
                # current item should also be included in new branches
                tasks = [asyncio.ensure_future(self.itemPoller(item))]

                for newItem in items_to_add:
                    tasks.append(asyncio.ensure_future(self.itemPoller(newItem, RECURSION_DEPTH=RECURSION_DEPTH + 1)))

                await asyncio.gather(*tasks)

                # if this is reached, all branched including the one that was responsible for current scope's item
                # were terminated which means that return is to be called
                return

            try:
                await self.refreshItemInfo(item, skip_csgo_float_request)
                skip_csgo_float_request = False
            except Exception as e:
                self.logger.exception(e)

    async def dbPoller(self):
        while True:
            await self.loadItemList()
            hour = 60 * 60
            await asyncio.sleep(hour)

    async def filesPoller(self):
        while True:
            await self.saveFiles()
            self.logger.info('saved files')
            await asyncio.sleep(600)

    async def loadItemList(self):
        #  load instances of csm overpay analyzers and a list of all items with any records
        float_data = await CsmFloatOverpayRecords().get_all_records()
        float_curves = {}

        for item_name in float_data:
            try:
                item_record = (await ItemsInfoRepository().get_item(item_name))
            except KeyError:
                continue

            float_range = (item_record.min_float, item_record.max_float)

            try:
                float_curves[item_name] = FloatCurve(float_data[item_name], item_name, float_range)
            except FloatCurve.NotEnoughDataPointsError:
                continue

        pattern_overpay_data = await CsmPatternOverpayRecords().get_all_records()
        pattern_overpay_instances = {}

        for item_name in pattern_overpay_data:
            pattern_overpay_instances[item_name] = PatternOverpay(pattern_overpay_data[item_name], item_name)

        all_items = list(set(pattern_overpay_instances.keys()) | set(float_curves.keys()))

        # items such that there are too many of them in inventory already
        blacklist = [item for item, count in (await InventoryRepository().get_item_count_dict()).items() if count > self.cfg['max_inv_items']]
        blacklist += self.cfg['blacklist']

        # all items with profit records that are not in the blacklist
        all_items = list(filter(lambda name: all([blocked_name.lower() not in name.lower() for blocked_name in blacklist]), all_items))

        # this should be eventually made True
        # these flags determine weather corresponding metric is used in evaluating profitability
        consider_new_listings_volume = True
        consider_item_price = True

        self.itemData = await dataLayer.marketInfo.MarketInfoRepository().get_dict()

        def get_profit_expectancy(x: str):
            overpay = 0

            # probability of a random item to exceed profit threshold set in cfg
            float_overpay_p = 0
            pattern_overpay_p = 0

            if x in float_curves:
                overpay += float_curves[x].get_overpay_expectancy()
                float_overpay_p = float_curves[x].get_deal_p()

            if x in pattern_overpay_instances:
                overpay += pattern_overpay_instances[x].get_overpay_expectancy()

            # 1 - *probability of both outcomes not happening*
            total_deal_p = 1 - (1 - float_overpay_p) * (1 - pattern_overpay_p)

            if x in self.itemData:
                new_listings_volume = self.itemData[x].daily_volume
                deals_per_day = new_listings_volume * total_deal_p

                # reasonable to expect not more than 1 deal per day
                max_deals_per_day = 1

                # If the number expected deals per day is greater than max_deals_per_day
                # adjust new_listings_volume so that item would not benefit from a big amount of illiquid deals.
                # This can't be done on a level of float_curve.get_over_expectancy because
                # that would violate the idea of profit expectancy from a single item.

                if deals_per_day > max_deals_per_day:
                    new_listings_volume *= max_deals_per_day / deals_per_day

                avg_price = self.itemData[x].avg_sell_price
            else:
                # item with no entry in itemData shouldn't be parsed
                new_listings_volume = 0
                avg_price = 0

            return overpay * (avg_price if consider_item_price else 1) * (new_listings_volume if consider_new_listings_volume else 1)


        all_items.sort(key=get_profit_expectancy, reverse=True)
        all_items[0] = "M4A1-S | Basilisk (Field-Tested)" #0.19392031431198
        items_to_parse = set(all_items[:self.cfg['items_to_parse']])

        for item in items_to_parse:
            if item not in self.item_list_profit:
                self.items_to_add_profit.append(item)

        self.item_list_profit = items_to_parse

    async def processNewDeal(self, deal: Deal):
        item_price = deal.price
        default_price = self.itemData[deal.itemName].avg_sell_price
        overpay = await predictProfit(deal, force_cache=True)

        if default_price is None:
            self.logger.debug(f'default price is None - {deal.itemName}')
            return

        if overpay is None:
            self.logger.debug(f'overpay is None - {deal.itemName}')
            return

        sell_price = (1 + overpay) * default_price * 0.88
        relative_profit = sell_price / item_price - 1
        absolute_profit = sell_price - item_price
        if sell_price / 100 > self.max_auto_sell_price:
            deal.buyingReason = 'profit_vip'
        else:
            deal.buyingReason = 'profit'

        if (str(deal.itemFloat) == "0.19392031431198") \
                or (relative_profit > self.cfg['min_relative_profit'] and absolute_profit / 100 > self.cfg['min_abs_profit'] \
                and overpay > self.cfg['min_relative_profit']):

            for accountName in self.buyingAccounts:
                with open(f"data/deals/{accountName}/{deal.mValue}.pkl", 'wb') as file:
                    pickle.dump(deal, file, pickle.HIGHEST_PROTOCOL)

            self.logger.critical('trying to buy an item')

            # wait for the attempt to buy the item
            await asyncio.sleep(60)

            # remove item from the parsing pool if updated quantity exceeds threshold
            condition = InventoryRepository.Record(
                item_name=deal.itemName,
                item_type='profit'
            )

            if len(await InventoryRepository().select(condition)) >= self.cfg['max_inv_items']:
                self.item_list_profit.remove(deal.itemName)

    async def proccessNewItem(self, name, listing):
        # print(f'{name} new item: {listing["m"]}')
        m = listing['m']

        item_info = await get_float_pattern_stickers(m, listing['a'], listing['d'])

        if item_info is None:
            return

        float_val, pattern, stickers = item_info

        deal = Deal(itemName=name, price=listing['price'], fee=listing['fee'], itemFloat=float_val, pattern=pattern,
                    stickers=stickers, mValue=m)

        await self.processNewDeal(deal)

    async def processItemPage(self, name: str, skip_csgo_float_request: bool):
        listings_info = await getPageListingsInfo(name, self.cfg['page_size'], cached=False)

        if listings_info is None:
            return None

        listings_found = set()
        tasks = []
        new_listings_count = 0

        for listing in listings_info:
            m = listing['m']
            listings_found.add(m)

            if m in self.itemCache[name]:
                continue

            new_listings_count += 1
            self.itemCache[name].add(m)
            if skip_csgo_float_request:
                continue

            tasks.append(asyncio.ensure_future(self.proccessNewItem(name, listing)))
        if not skip_csgo_float_request:
            await asyncio.gather(*tasks)

        return listings_found

    async def refreshItemInfo(self, name: str, skip_csgo_float_request: bool):
        if name not in self.itemData:
            await asyncio.sleep(1)
            return

        if name not in self.itemCache:
            self.itemCache.update({name: set()})

        listings_found = await self.processItemPage(name, skip_csgo_float_request)

        if listings_found is None:
            return

        return

    async def saveFiles(self):
        await self.fileWriter.proccesWriting(getJsonedCache(self.itemCache), 'data/', 'autoItemCache.json')


if __name__ == '__main__':
    parser = PatternScrapper()
    asyncio.run(parser.main())
