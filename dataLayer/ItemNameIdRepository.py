import dataclasses

from soldiersORM.OrmBase import OrmBase


class ItemNameIdRepository(OrmBase):
    table_name = 'item_name_ids'

    @dataclasses.dataclass
    class Record(OrmBase.Record):
        name: str = None
        item_name_id: int = None

    async def add_record(self, name, itemNameId):
        await self.insert(self.Record(
            name=name,
            item_name_id=itemNameId
        ))

    async def delete_record(self, itemName):
        condition = self.Record(
            name=itemName
        )
        await self.remove_record(condition)

    async def get_all_as_dict(self) -> dict:
        return {record.name: record.item_name_id for record in await self._select_all()}