def run():
    from marketParser import WithdrawalParser
    from dataLayer.ItemNameIdRepository import ItemNameIdRepository
    from steam.Analyzers import SimpleSteamAnalyzer
    from plznomarket import SimplePlznomarketAnalyzer

    items = [record.name for record in ItemNameIdRepository().blocking()._select_all()]

    WithdrawalParser(items, SimpleSteamAnalyzer(), [SimplePlznomarketAnalyzer()]).startParsingThreads(numberOfThreads=1)


if __name__ == '__main__':
    while True:
        run()
