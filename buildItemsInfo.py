import time

import requests
from bs4 import BeautifulSoup
from dataLayer.ItemsInfoRepository import ItemsInfoRepository


url = 'https://csgostash.com/skin'

def getFloatRange(pageSoup: BeautifulSoup) -> tuple[float, float]:
    divs = pageSoup.findAll('div', {'class': 'marker-value cursor-default'})
    return (float(divs[0].text), float(divs[1].text))

def getShortName(pageSoup: BeautifulSoup) -> str:
    return pageSoup.find('div', {'class': 'well result-box nomargin'}).find('h2').text

def getStattrack(pageSoup: BeautifulSoup) -> bool:
    return bool(pageSoup.find('div', {'class': 'stattrak'}))

def getPageSoup(pageNumber: int) -> BeautifulSoup | None:
    res = None

    for i in range(3):
        try:
            res = requests.get(url + f'/{pageNumber}')

            if res.status_code == 404:
                print(404)
                return None
        except Exception as e:
            time.sleep(10)

    if res is None:
        return None

    print(res)
    return BeautifulSoup(res.text, features="html.parser")

def parsePage(pageNumber: int) -> None:
    soup = getPageSoup(pageNumber)

    if soup is None:
        return None

    #положить вот это в дб

    try:
        res = (getStattrack(soup), getFloatRange(soup), getShortName(soup))
    except Exception as e:
        return None

    if None in res:
        return None

    ItemsInfoRepository().blocking().remove_record(ItemsInfoRepository.Record(
        item_name=res[2]
    ))

    ItemsInfoRepository().blocking().insert(ItemsInfoRepository.Record(
        st=res[0],
        min_float=res[1][0],
        max_float=res[1][1],
        item_name=res[2]
    ))

if __name__ == '__main__':
    for i in range(7, 10000):
        for _ in range(3):
            try:
                parsePage(i)
                time.sleep(10)
                break
            except Exception as e:
                print(e)
                time.sleep(10)
