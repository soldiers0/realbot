import logging

from marketParser import MarketParser
from models import AbstractAnalyzer
from csmoney.csmoneyRequests import getSkinsInfo, getItemInfoCsm
from dataLayer.CsmFloatOverpayRecords import CsmFloatOverpayRecords as db
from config.cfg import config


class CsMoneyParser(MarketParser):
    def __init__(self, skinsToParse: list[str], steamAnalyzer: AbstractAnalyzer):
        super().__init__(skinsToParse)

        self.rate = config()["dollarToEuroExchangeRate"]
        self.cfg = config()["csmoneyParser"]
        self.steamAnalyzer = steamAnalyzer

        if not hasattr(self, 'logger'):
            self.logger = logging.getLogger()

    def analyzeItem(self, name: str) -> None:
        skinsInfo = getSkinsInfo(name)  # тут вся инфа с флоатами и оверпеями по всем скинам со страницы

        if skinsInfo is None:
            self.logger.warning(f'could not load skins info - {name}')
            return

        if skinsInfo == []:
            self.logger.info(f'no skins on csm - {name}')
            return

        skinData = None

        for sample in skinsInfo:
            requestId = sample['assetId']
            skinData = getItemInfoCsm(requestId, name)  # это старый запрос дефолт прайс и оверсток есть только там

            if skinData is not None:
                break

        if skinData is None:
            self.logger.warning(f'could not get skin data for - {name}')
            return None

        defaultPrice = skinData['defaultPrice']

        if defaultPrice * 2 * self.rate < self.cfg["min_abs_profit"]:
            self.logger.info(f'price is too low - {name}')
            return

        if defaultPrice * self.rate > self.cfg["max_price"]:
            self.logger.info(f'price is too high - {name}')
            return

        records = []

        for skin in skinsInfo:
            if name != skin['fullName']:
                continue

            if skin['overpay'] is None or 'float' not in skin['overpay']:
                continue

            floatOverpay = skin['overpay']['float'] / defaultPrice

            skinFloat = float(skin['float'])
            records.append((skinFloat, floatOverpay, defaultPrice * self.rate))

        if len(records) < 2:
            self.logger.info(f'not enough data points for {name}')
            return

        db().blocking().delete_all_item_records(name)

        self.logger.info(f'found {len(records)} data points for {name}')

        for record in records:
            db().blocking().add_record(name, *record)
