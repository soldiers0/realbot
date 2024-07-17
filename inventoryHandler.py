import asyncio
import time

from tools.itemTools import getFloat
from steam.AccountHandler import AccountHandler
from steam.Analyzers import PriceChartSteamAnalyzer
from dataLayer.InvenoryRepository import InventoryRepository
from csgofloat import get_float_pattern_stickers
from csmoney.csmOverpayAnalyzers import predictProfit
from requestHandler import TooManyRequests


class InventoryHandler(AccountHandler):
    def __init__(self, accountName, steam_analyzer: PriceChartSteamAnalyzer = PriceChartSteamAnalyzer()):
        super().__init__(accountName)
        self.steam_analyzer = steam_analyzer
        self.current_total_market_actions = None

    def manageSteamInventory(self):
        db_items = InventoryRepository().blocking().get_account_inventory(self.account.username)
        db_items: list[InventoryRepository.Record]
        self.cancelAllListings()
        inv_items = self.get_inventory(onlySkins=True)

        for db_entry in db_items:
            inv_item_info = inv_items.get(db_entry.item_id)

            if inv_item_info is None:  # item not in inventory

                InventoryRepository().blocking().delete_item(db_entry.item_id)
                self.logger.info(f'removing {db_entry.item_name} from db')
                continue

            tradable = inv_item_info['tradable']
            asset_id = inv_item_info['a']
            item_name = inv_item_info['name']

            if tradable and db_entry.current_account != db_entry.account_to_transfer:
                partner_account_handler = AccountHandler(db_entry.account_to_transfer)
                trade_id = self.transferItems(asset_id, partner_account_handler.account.steam_id)

                if trade_id is not None and partner_account_handler.acceptTrade(trade_id):
                    InventoryRepository().blocking().mark_item_transferred(db_entry.item_id)

                continue

            if db_entry.item_type in ('profit', 'float'):  # float entry type is redundant was used for debug
                args = (inv_item_info['ms'], inv_item_info['a'], inv_item_info['d'])
                overpay = predictProfit(*asyncio.run(get_float_pattern_stickers(*args, fromInventory=True)), item_name)
                overpay = asyncio.run(overpay)

                timestamp = db_entry.last_action.timestamp()
                time_elapsed = time.time() - timestamp
                day = 60 * 60 * 24
                days_elapsed = time_elapsed / day

                # through the first week overpay will fall to half of its original valu
                overpay_deterioration = overpay / 2 * min(days_elapsed, 7) / 7
                overpay -= overpay_deterioration

                if overpay <= 0:
                    self.logger.info(f'no profit info for {item_name}')
                    continue

                while True:
                    try:
                        sell_price = self.steam_analyzer.getSellPrice(item_name, account_name=self.accountName)
                    except TooManyRequests:
                        sell_price = None
                        time.sleep(120)
                        self.logger.warning('too many requests while fetching price chart, sleeping for 2 mins')

                    if sell_price is not None:
                        break

                self.sellItem(asset_id, int(sell_price * (1 + overpay)))

            if db_entry.item_type == 'steam':
                while True:
                    try:
                        sell_price = self.steam_analyzer.getSellPrice(item_name, account_name=self.accountName)
                    except TooManyRequests:
                        sell_price = None
                        time.sleep(120)
                        self.logger.warning('too many requests while fetching price chart, sleeping for 2 mins')

                    if sell_price is not None:
                        break

                self.sellItem(asset_id, int(sell_price))
                time.sleep(5)

    def setInventory(self):
        """
        add records about items in inventory by hand
        """
        self.cancelAllListings()

        inv = self.get_inventory(onlySkins=True)
        db_items = InventoryRepository().blocking().get_account_inventory(self.account.username)

        if input('reset tracked items? y/n').lower() == 'y':
            for item in inv:
                name = inv[item]['name']
                a = inv[item]['a']
                ms = inv[item]['ms']
                d = inv[item]['d']

                itemFloat = getFloat(ms, a, d)

                inv[item]['float'] = itemFloat

                itemHash = item

                print(name, itemFloat)
                order_type = input()

                InventoryRepository().blocking().insert(InventoryRepository.Record(
                    item_id=itemHash,
                    current_account=self.account.username,
                    account_to_transfer=self.account.username,
                    item_type=order_type,
                    item_name=name
                ))

        for db_item in db_items:
            if db_item.itemId not in inv:
                if input(f'delete {db_item.item_name} with type {db_item.type} from db? y/n').lower() == 'y':
                    InventoryRepository().blocking().delete_item(db_item.itemId)


def fix_inventory_repo():
    ah = AccountHandler('realchelovek')
    ah.cancelAllListings()
    inv = ah.get_inventory(onlySkins=True)
    db_items = InventoryRepository().blocking().get_account_inventory(ah.account.username)

    for db_item in db_items:
        InventoryRepository().blocking().delete_item(db_item.itemId)

        if db_item.itemId in inv:
            db_item.item_name = inv[db_item.itemId]['name']
            InventoryRepository().blocking().insert(db_item)


if __name__ == '__main__':
    while True:
        InventoryHandler('realchelovek').manageSteamInventory()
        hour = 60 * 60
        time.sleep(hour * 4)
