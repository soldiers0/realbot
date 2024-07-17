from csmoney.csmoneyParser import CsMoneyParser
from dataLayer.ItemsInfoRepository import ItemsInfoRepository
def pollingCsmParsing():
    items_to_parse = ItemsInfoRepository().blocking().get_all_names()

    from steam.Analyzers import SimpleSteamAnalyzer
    csm_parser = CsMoneyParser(items_to_parse, SimpleSteamAnalyzer())

    number_of_threads = int(input('number of threads: '))

    while True:
        csm_parser.startParsingThreads(numberOfThreads=number_of_threads)


if __name__ == '__main__':
    pollingCsmParsing()
