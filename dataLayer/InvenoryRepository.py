import dataclasses
import datetime

from soldiersORM.OrmBase import OrmBase


class InventoryRepository(OrmBase):
    table_name = 'inventory'

    @dataclasses.dataclass
    class Record(OrmBase.Record):
        item_id: str = None
        current_account: str = None
        account_to_transfer: str = None
        item_type: str = None
        item_name: str = None
        last_action: datetime.datetime = datetime.datetime.now()
        game: str = 'csgo'

    async def change_target_account(self, item_id: str, transfer_to: str):
        condition = self.Record(
            item_id=item_id
        )

        item = (await self.select(condition))[0]
        await self.remove_record(condition)
        item.account_to_transfer = transfer_to
        await self.insert(item)

    async def mark_item_transferred(self, item_id: str):
        condition = self.Record(
            item_id=item_id
        )

        item = (await self.select(condition))[0]
        await self.remove_record(condition)
        item.account_to_transfer = item.current_account
        await self.insert(item)

    async def get_account_inventory(self, account):
        condition = self.Record(
            current_account=account
        )

        return await self.select(condition)

    async def get_item_count_dict(self, types: list = None) -> dict[str, int]:
        """
        returns amount of item across all accounts
        by default, only profit items are accounted for
        """

        if types is None:
            types = ['profit']

        items = await self._select_all()

        res = {}

        for item in items:
            if item.item_type in types:
                if item.item_name not in res:
                    res[item.item_name] = 0

                res[item.item_name] += 1

        return res

    async def delete_item(self, item_id: str):
        condition = self.Record(
            item_id=item_id
        )
        await self.remove_record(condition)

    async def insert(self, record: Record) -> None:
        if record.last_action is None:
            record.last_action = datetime.datetime.now()

        await super().insert(record)
