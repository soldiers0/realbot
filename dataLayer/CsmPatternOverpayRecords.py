import dataclasses

from dataLayer.CsmFloatOverpayRecords import CsmFloatOverpayRecords
from soldiersORM.OrmBase import OrmBase


class CsmPatternOverpayRecords(CsmFloatOverpayRecords):
    table_name = 'csm_pattern_overpay_records'

    @dataclasses.dataclass
    class Record(OrmBase.Record):
        pattern: int = None
        overpay: float = None
        item_name: str = None
        cs_money_price: float = None


if __name__ == '__main__':
    print(CsmPatternOverpayRecords.delete_all_item_records("new"))
