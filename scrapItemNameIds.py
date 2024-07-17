import asyncio
from dataLayer.ItemNameIdRepository import ItemNameIdRepository
from dataLayer.ItemsInfoRepository import ItemsInfoRepository
from steam.steam_requests import getItemNameId


def run():
    while True:
        all_records = set(ItemNameIdRepository().blocking().get_all_as_dict().keys())

        for name in ItemsInfoRepository().blocking().get_all_names():
            if name not in all_records:
                try:
                    itemNameId = asyncio.run(getItemNameId(name))

                    if itemNameId is None:
                        continue

                    print(name, int(itemNameId))
                    ItemNameIdRepository().blocking().delete_record(name)
                    ItemNameIdRepository().blocking().add_record(name, itemNameId)
                except Exception as e:
                    print(e)

if __name__ == '__main__':
    run()