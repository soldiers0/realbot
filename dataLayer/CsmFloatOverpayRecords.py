from dataclasses import dataclass
from collections import defaultdict
from soldiersORM.OrmBase import OrmBase


class CsmFloatOverpayRecords(OrmBase):
    table_name = 'csm_float_overpay_records'

    @dataclass
    class Record(OrmBase.Record):
        item_name: str = None
        item_float: float = None
        overpay: float = None
        cs_money_price: float = None

    async def add_record(self, item_name, item_float, overpay, cs_money_price):
        await self.insert(self.Record(
            item_name=item_name,
            item_float=item_float,
            overpay=overpay,
            cs_money_price=cs_money_price
        ))

    async def get_all_records(self) -> dict[str, list[Record]]:
        res = defaultdict(list)
        all_records = await self._select_all()

        for record in all_records:
            res[record.item_name].append(record)

        return res

    async def delete_all_item_records(self, item_name):
        condition = self.Record(item_name=item_name)
        await self.remove_record(condition)
