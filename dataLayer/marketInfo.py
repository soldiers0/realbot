from soldiersORM.OrmBase import OrmBase
from dataclasses import dataclass


class MarketInfoRepository(OrmBase):
    table_name = 'market_info'

    @dataclass
    class Record(OrmBase.Record):
        item_name: str = None
        avg_sell_price: float = None
        daily_volume: float = None

    async def update_item_data(self, record: Record) -> None:
        assert record.item_name is not None

        await self.remove_record(self.Record(item_name=record.item_name))
        await self.insert(record)

    async def get_dict(self) -> dict[str, Record]:
        return {record.item_name: record for record in await self._select_all()}


if __name__ == '__main__':
    res = MarketInfoRepository(debug=True).blocking().get_dict()
    print('хуй')
