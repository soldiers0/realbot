from dataLayer.CsmFloatOverpayRecords import CsmFloatOverpayRecords
from marketParser import ProxySteamParser
if __name__ == '__main__':
    ProxySteamParser(list(CsmFloatOverpayRecords(debug=True).blocking().get_all_records().keys())).startParsingThreads(
        numberOfThreads=2
    )