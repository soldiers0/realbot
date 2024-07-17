from requestHandler import RequestHandler
from tools.itemTools import normalizeStickers, getDopplerPattern

csgofloat_cache = {}
max_csgofloat_cache_size = 1000
host = "http://194.36.161.123:8002"

async def makeCSGOFloatQuery(*args, fromInventory=False):
    """either pass 3 values of ms a d or an inspect link"""
    if len(args) == 1:
        url = f'{host}/?url={args[0]}'
    elif fromInventory:
        url = f'{host}/?m={args[0]}&a={args[1]}&d={args[2]}'
    else:
        url = f'{host}/?s={args[0]}&a={args[1]}&d={args[2]}'

    if url in csgofloat_cache:
        return csgofloat_cache[url]

    response = await RequestHandler.get(url, cached=True, timeout=10)

    if response is None or response['json'] is None:
        return None

    response = response['json']

    if len(csgofloat_cache) < max_csgofloat_cache_size:
        csgofloat_cache[url] = response['iteminfo']

    return response['iteminfo']


async def get_float_pattern_stickers(*args, fromInventory=False) -> tuple[float, int, str] | None:
    item_info = await makeCSGOFloatQuery(*args, fromInventory=fromInventory)

    if item_info is None:
        return None

    float_value: float = item_info['floatvalue']
    pattern = int(item_info['paintseed'])
    stickers = normalizeStickers(item_info['stickers'])

    if 'Doppler' in item_info['full_item_name']:
        pattern = getDopplerPattern(item_info['imageurl'])

    return (float_value, pattern, stickers)

