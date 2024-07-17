import json

import pandas as pd
import requests
from requestHandler import RequestHandler
from config.cfg import config

steam_market_url = 'https://steamcommunity.com/market'


async def getItemNameId(name, cached=True):
    url = f'{steam_market_url}/listings/730/{name}?count=1&start=0&country=RU&currency={config()["currency"]}'
    response = await RequestHandler.get(url, cached=cached, timeout=10)

    if response is None or response['text'] is None:
        return None

    response = response['text']

    chunk = response[response.find('Market_LoadOrderSpread'):response.find('Market_LoadOrderSpread', response.find(
        'Market_LoadOrderSpread') + 1):]

    if len(chunk.split()) >= 2:
        return chunk.split()[1]
    else:
        return None


async def getHighestBuyOrder(nameid, cached=True):
    url = f'{steam_market_url}/itemordershistogram?country=RU&language=russian&currency={config()["currency"]}' \
          f'&item_nameid={nameid}&two_factor=0'
    response = None

    response = await RequestHandler.get(url, cached=cached, timeout=10)

    if response is None or response['json'] is None:
        return None

    response = response['json']

    if 'highest_buy_order' in response:
        return response['highest_buy_order']
    else:
        return None


async def getLowestSellOrder(nameid, cached=True):
    url = f'{steam_market_url}/itemordershistogram?country=RU&language=russian&currency={config()["currency"]}' \
          f'&item_nameid={nameid}&two_factor=0'

    response = await RequestHandler.get(url, cached=cached, timeout=10)

    if response is None or response['json'] is None:
        return None

    response = response['json']

    if 'lowest_sell_order' in response:
        return response['lowest_sell_order']


async def getPageListingsInfo(name, pageSize, cached=False):
    url = f'{steam_market_url}/listings/730/{name}/render/?query=&start=0' \
          f'&count={pageSize}&country=RU&language=english&currency={config()["currency"]}'
    response = await RequestHandler.get(url, cached=cached, timeout=10)

    if response is None or response['text'] is None:
        return None

    response = response['text']

    try:
        data = json.loads(response)
    except:
        return None

    if data is None:
        return None

    if 'success' not in data or not data['success']:
        return None

    data = data['listinginfo']

    pos = 0
    res = []

    if data == []:  # это происходит если страница пустая
        return []

    foundItems = False

    for entry in data:
        if 'converted_fee' not in data[entry]:
            continue

        item = data[entry]
        m = entry
        a = str(item['asset']['id'])

        if 'market_actions' not in item['asset']:
            print(f'{url} - no market actions')

        d = item['asset']['market_actions'][0]['link']
        d = d[d.find('id%D') + 4::]
        link = f'steam://rungame/730/76561202255233023/+csgo_econ_action_preview M{m}A{a}D{d}'
        fee = data[entry]['converted_fee']
        price = data[entry]['converted_price'] + fee

        res.append({
            'm': m,
            'a': a,
            'd': d,
            'link': link,
            'price': price,
            'fee': fee,
            'position': pos
        })

        foundItems = True

        pos += 1

    # print(len(res),f'proxy: {proxy}', name)
    if not foundItems:
        return None

    return res


async def getItemSellInfo(name, cached=True):
    url = f'{steam_market_url}/priceoverview/?appid=730&currency={config()["currency"]}&market_hash_name={name}'

    response = await RequestHandler.get(url, cached=cached, timeout=10)

    if response is None or response['json'] is None:
        return None

    response = response['json']

    return response


async def get_listings_page(item_name, account_name=None, use_proxy=False, cached=False) -> str | None:
    """
    fetches the raw listings page, as opposed to a json query with items
    """
    url = f'{steam_market_url}/listings/730/{item_name}'

    if use_proxy:
        response = await RequestHandler.get(url, cached=cached, timeout=10)

        if response is None or response['text'] is None:
            return None

        text = response['text']
    else:
        from steam.AccountHandler import AccountHandler

        if account_name is not None:
            session = AccountHandler(account_name).get_session()
        else:
            session = requests.Session()

        response = session.get(url, timeout=10)

        if response.status_code == 429:
            from requestHandler import TooManyRequests
            raise TooManyRequests()

        if not response.ok:
            return None

        text = response.text

    return text


async def get_sell_price_history(item_name, account_name=None, use_proxy=False, cached=False) -> pd.DataFrame | None:
    """
    if account_name is passed its session is used, that is the only way to get price chart in rubles.
    if use_proxy is true, request is performed via requestHandler, result will be in dollars and converted to rubles
    otherwise request is done from bare ip of the machine without proxy or logged session, final result is also
    converted
    """
    import datetime

    text = await get_listings_page(item_name, account_name, use_proxy, cached)
    if text is None:
        return None

    exchange_rate = config()['dollarToEuroExchangeRate']
    # if a dollar sign is in the html page, the price chart is plotted in dollars
    if '$' not in text:
        exchange_rate = 1

    price_history_chunk = text[text.find('[["'): text.find(']];') + 2]

    try:
        res = json.loads(price_history_chunk)
        dates = []
        prices = []

        for record in res:
            timestamp = datetime.datetime.strptime(record[0].split(':')[0], "%b %d %Y %H")
            prices.extend(float(record[1]) * exchange_rate for _ in range(int(record[2])))
            dates.extend(timestamp for _ in range(int(record[2])))

        return pd.DataFrame(prices, index=dates, columns=['Price'])
    except:
        return None


async def get_cheapest_item(item_name, account_name=None, use_proxy=False, cached=False) -> dict | None:
    text = await get_listings_page(item_name, account_name, use_proxy, cached)

    if text is None:
        return None

    start_of_section = text.find('var g_rgListingInfo = ') + len('var g_rgListingInfo = ')
    end_of_section = text.find('var g_plotPriceHistory = null;') - 4

    listings_json = text[start_of_section: end_of_section]
    data: dict = json.loads(listings_json)
    entry = next(iter(data.keys()))

    if 'converted_fee' not in data[entry]:
        return None

    item = data[entry]
    m = entry
    a = str(item['asset']['id'])
    d = item['asset']['market_actions'][0]['link']
    d = d[d.find('id%D') + 4::]
    link = f'steam://rungame/730/76561202255233023/+csgo_econ_action_preview M{m}A{a}D{d}'
    fee = data[entry]['converted_fee']
    price = data[entry]['converted_price'] + fee

    return {
        'm': m,
        'a': a,
        'd': d,
        'link': link,
        'price': price,
        'fee': fee,
    }
