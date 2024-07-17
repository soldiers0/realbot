import dataclasses

from tools import itemTools
from soldiersORM.OrmBase import OrmBase


class ItemsInfoRepository(OrmBase):
    table_name = 'items_info'
    item_dict = None

    @dataclasses.dataclass
    class Record(OrmBase.Record):
        min_float: float = None
        max_float: float = None
        st: bool = None
        item_name: str = None

        def getConditions(self):
            res = []

            conditions = {
                '(Factory New)': [0, 0.07],
                '(Minimal Wear)': [0.07, 0.15],
                '(Field-Tested)': [0.15, 0.38],
                '(Well-Worn)': [0.38, 0.45],
                '(Battle-Scarred)': [0.45, 1]
            }

            for condition, floatRange in conditions.items():
                if self.min_float <= floatRange[0]:  # --L-|------|-----
                    if self.max_float >= floatRange[0]:  # ---L-|--R---|---
                        res.append(condition)
                    continue

                if self.min_float < floatRange[1]:  # --|-L-----|
                    res.append(condition)
                    continue

            return res

        def getStPrefixes(self):
            res = ['']

            if self.st:
                res.append('StatTrak™ ')

            if '\u2605' in self.item_name:
                return ['\u2605' + ' ' + prefix for prefix in res]

            return res

        def getAllPossibleNames(self):
            """
            returns all names for particular skin
            """
            return [prefix + self.item_name[2 * int('\u2605' in self.item_name):] + ' ' + suffix for prefix in
                    self.getStPrefixes()
                    for suffix in self.getConditions()]

    async def get_item(self, itemName: str, force_load=False):
        item_dict = await self.get_items_dict(force_load=force_load)

        try:
            return item_dict[itemName]
        except KeyError:
            return item_dict[itemTools.getBasicName(itemName)]

    async def get_items_dict(self, force_load=False) -> dict[str, Record]:
        items_dict = {}

        if self.item_dict is not None and not force_load:
            return self.item_dict

        records = await self._select_all()

        for record in records:
            name = itemTools.addStarToFullname(record.item_name)
            items_dict[name] = record

        self.__class__.item_dict = items_dict
        return items_dict

    async def delete_item(self, itemName):
        condition = self.Record(
            item_name=itemName
        )

        await self.remove_record(condition)

    async def get_all_names(self, force_load=False) -> list[str]:
        res = []

        for record in (await self.get_items_dict(force_load=force_load)).values():
            res.extend(record.getAllPossibleNames())

        return res
