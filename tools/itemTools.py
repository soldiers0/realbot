import hashlib
import time
import random
import requests
import asyncio


def getFloat(*args, fromInventory=False) -> str:
    from csgofloat import makeCSGOFloatQuery
    while True:
        res = asyncio.run(makeCSGOFloatQuery(*args, fromInventory=fromInventory))

        if res is not None:
            break

        time.sleep(5)

    floatValue = res['floatvalue']
    return str(floatValue)


def getMarketHashName(*args, fromInventory=False) -> str:
    from csgofloat import makeCSGOFloatQuery
    while True:
        res = asyncio.run(makeCSGOFloatQuery(*args, fromInventory=fromInventory))

        if res is not None:
            break

        time.sleep(5)
    name = res['full_item_name']
    return name


def getHashFromInspect(*args, fromInventory=False) -> int:
    text = getMarketHashName(*args, fromInventory=fromInventory) + getFloat(*args, fromInventory=fromInventory)[:6]
    return int(hashlib.md5(text.encode('utf-8')).hexdigest(), 16)


def getMinFloatByFloat(float):
    if float > 0.5:
        return 0.5
    if float > 0.35:
        return 0.35
    if float > 0.15:
        return 0.15
    if float > 0.07:
        return 0.07
    return 0


def getHash(itemName, itemFloat=None):
    if itemFloat is None:
        text = itemName
    else:
        text = itemName + str(itemFloat)[:6:]

    return int(hashlib.md5(text.encode('utf-8')).hexdigest(), 16)


def isSkin(itemName):
    for q in ['Battle-Scarred', 'Well-Worn', 'Field-Tested', 'Minimal Wear', 'Factory New']:
        if q in itemName:
            return True

    return False


def getNextRarity(rarity):
    options = ['Consumer grade', 'Industrial grade', 'Mil-spec', 'Restricted', 'Classified', 'Covert', None]
    it = 0

    for option in options:
        if options[it] == None:
            return None

        if options[it] == rarity:
            return options[it + 1]

        it += 1


def getNextQuality(rarity):
    options = ['Battle-Scarred', 'Well-Worn', 'Field-Tested', 'Minimal Wear', 'Factory New', None]
    it = 0

    for option in options:
        if options[it] == None:
            return None

        if options[it] == rarity:
            return options[it + 1]

        it += 1


def getCheapestItem(collectionsDict, collection, rarity, quality):
    if rarity not in collectionsDict[collection]:
        return None

    options = collectionsDict[collection][rarity]
    minPrice = 228e1337
    answer = None
    for item in options:
        if options[item][quality] >= 0 and options[item][quality] < minPrice:
            minPrice = options[item][quality]
            answer = item

    return answer


def getAvgFloat(quality):
    floatDict = {
        'Battle-Scarred': 0.725,
        'Well-Worn': 0.415,
        'Field-Tested': 0.265,
        'Minimal Wear': 0.11,
        'Factory New': 0.35
    }

    if quality not in floatDict:
        return None

    return floatDict[quality]


def getTradeUpOutputQuality(avgInputFloat, minFloat, maxFloat):
    resFloat = (maxFloat - minFloat) * avgInputFloat + minFloat

    if resFloat <= 0.07:
        return 'Factory New'

    if resFloat <= 0.15:
        return 'Minimal Wear'

    if resFloat <= 0.38:
        return 'Field-Tested'

    if resFloat <= 0.45:
        return 'Well-Worn'

    return 'Battle-Scarred'


def getBasicName(name: str):
    if 'stattrak' in name.lower():
        name = ' '.join(name.split()[1:])

    if '(' in name:
        name = ' ('.join(name.split(' (')[:-1])

    return name


def getBasicNameBack(name, withQuality=True):
    strSplit = name.split()
    return strSplit.join(' ')


def getItemScreenShot(inspectLink, driver, lastScreen='None'):
    for i in range(5):
        try:
            time.sleep(0.5)
            driver.get("https://liquipedia.net/counterstrike/BLAST/Premier/2020/Fall/Showdown")
            time.sleep(0.5)
            driver.get("https://broskins.com/index.php?pages/csgo-skin-screenshot/")
            time.sleep(0.5)
            driver.find_element_by_id('inspect').send_keys(inspectLink)
            time.sleep(1)
            driver.find_element_by_id('sendbtn').click()
            time.sleep(0.5)
            pageSource = driver.page_source.split('"')
            for i in pageSource:
                if '_image.jpg' in i and 's1.cs.money' in i and i != lastScreen:
                    return i
            continue
        except Exception as e:
            print(f'get item screen shot {e}')
            continue
    return None


def getScreenshotGG(link):
    res = {}
    imageLink = None

    for i in range(5):
        try:
            data = {
                'inspectLink': link,
                'Authorization': open(f'data/swapggKeys/swapggKey{random.randint(1, 3)}.txt', 'r').read()
            }

            res = requests.post(f'https://market-api.swap.gg/v1/screenshot', json=data, timeout=15).json()
            print(res)
            break
        except Exception as e:
            print(e)
            time.sleep(5)

    if res == {}:
        return None

    for i in range(10):
        try:
            data = {
                'inspectLink': link,
                'Authorization': open(f'data/swapggKeys/swapggKey{random.randint(1, 3)}.txt', 'r').read()
            }

            res = requests.post(f'https://market-api.swap.gg/v1/screenshot', json=data).json()

            if 'imageLink' in res['result']:
                imageLink = res['result']['imageLink']
                break
        except Exception as e:
            print(e)

        time.sleep(15)

    if imageLink == None:
        return None

    res = None

    for i in range(10):
        try:
            res = requests.get(imageLink)

            if res.status_code != 200:
                res = None
            else:
                break
        except:
            pass

    if res == None:
        return None

    return res.content


def getFloatRangeFromCondition(condition):
    if '(' in condition:
        condition = condition[1:-1]

    conditions = {
        'Factory New': [0, 0.07],
        'Minimal Wear': [0.07, 0.15],
        'Field-Tested': [0.15, 0.38],
        'Well-Worn': [0.38, 0.45],
        'Battle-Scarred': [0.45, 1]
    }

    return conditions[condition]



def addStatTrackToFullName(name):
    res = ''
    nameSplit = name.split()

    if '★' in name:
        res += '★ StatTrak™'
        nameSplit.pop(0)
    else:
        res += 'StatTrak™'

    for string in nameSplit:
        res += (' ' + string)

    return res

def addStarToFullname(name):
    if "Knife" in name or "Gloves" in name or "Daggers" in name or "Wraps" in name:
        return "★ " + name
    return name

if __name__ == '__main__':
    while True:
        name = input()
        print(getBasicName(name))  # hydra_case_hardened862749493


def normalizeStickers(floatStickers):
    stickers = ""

    for sticker in floatStickers:
        stickers += ('Sticker | ' + sticker['name'] + ';')

    return stickers


def getDopplerPattern(imageUrl):
    if 'phase1' in imageUrl:
        return 'Phase1'

    if 'phase2' in imageUrl:
        return 'Phase2'

    if 'phase3' in imageUrl:
        return 'Phase3'

    if 'phase4' in imageUrl:
        return 'Phase4'

    if 'ruby' in imageUrl:
        return 'Ruby'

    if 'sapphire' in imageUrl:
        return 'Sapphire'

    if 'emerald' in imageUrl:
        return 'Emerald'

    if 'blackpearl' in imageUrl:
        return 'BlackPearl'

    return 'Error'


def removeRareItemsFromList(itemList: list):
    res = []

    for item in itemList:
        if '★' not in item:
            res.append(item)

    return res


def normalizeItemList(itemList: list):
    res = []

    for item in itemList:
        item = item.replace("@", "'")
        res.append(item)

    return res
