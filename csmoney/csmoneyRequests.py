import asyncio
import json

from requestHandler import RequestHandler
from tools.itemTools import addStatTrackToFullName


def getSkinsInfo(name) -> list | None:
    if 'StatTrak' in name:
        stattrakArg = 'true'
    else:
        stattrakArg = 'false'

    url = f'https://cs.money/ru/csgo/trade/?search={name}&sort=float&order=asc&hasTradeLock=true&hasTradeLock=false&isStatTrak={stattrakArg}&isSouvenir=false'

    response = asyncio.run(RequestHandler.get(url))

    if response is None or response['text'] is None:
        return None

    source = response['text']

    startParse = source.find('skinsInfo') + 11
    endParse = source.find('},"userInitData"')

    try:
        data = json.loads(source[startParse:endParse:])
    except:
        return None

    if data.get('error') == 2:
        return []

    return data.get('skins')

def getItemInfoCsm(id, fullName):
    url = f'https://cs.money/skin_info?appId=730&id={id}&isBot=true&botInventory=true'
    response = asyncio.run(RequestHandler.get(url))

    if response is None or response['json'] is None:
        return None

    response = response['json']

    try:
        assert response['steamName'] == fullName or response['steamName'] == addStatTrackToFullName(fullName)
    except AssertionError:
        return None

    return response
