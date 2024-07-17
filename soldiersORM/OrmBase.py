import asyncio
import datetime
from dataclasses import dataclass
from soldiersORM.DBTools import DBTools


class OrmBase:
    """
    Base class for all operations with soldiersOrm.
    Each inherited class has to define its own inner Record class
    Class methods are absent to force the __init__ call which performs a setup of the database
    """
    table_name = None
    schema: dict[str, type] = None
    is_initialized = False
    _next_call_blocking = False
    _setup_task = None

    class NoTableNameSpecified(Exception):
        def __init__(self):
            super().__init__('No table name specified')

    @dataclass
    class Record:
        class EmptyRecordInitiated(Exception):
            def __init__(self):
                super().__init__('Empty record initiated')

        def to_db(self):
            """
            Prepares data for a sql query (replace single quotation marks and enclose str values with them)
            and returns modified self
            """
            new_obj = object.__new__(self.__class__)

            for attr_name in self.__dict__:
                if isinstance(self.__dict__[attr_name], str):
                    new_obj.__dict__[attr_name] = self.__dict__[attr_name].replace("'", "*")
                    new_obj.__dict__[attr_name] = "'" + new_obj.__dict__[attr_name] + "'"
                else:
                    new_obj.__dict__[attr_name] = self.__dict__[attr_name]

            return new_obj

        def from_db(self):
            """
            normalizes data (changes stars back to single quotation marks)
            returns changed self
            """
            new_obj = object.__new__(self.__class__)

            for attr_name in self.__dict__:
                if isinstance(self.__dict__[attr_name], str):
                    new_obj.__dict__[attr_name] = self.__dict__[attr_name].replace("*", "'")
                else:
                    new_obj.__dict__[attr_name] = self.__dict__[attr_name]

            return new_obj

    def __init__(self, debug=False):
        if self.table_name is None:
            raise self.NoTableNameSpecified

        if self.is_initialized:
            return

        from soldiersORM.dbSetup import setup

        try:
            # we are in a running loop
            loop = asyncio.get_running_loop()
            self._setup_task = loop.create_task(setup(self.__class__))
        except RuntimeError:
            # no current loop exists
            asyncio.run(setup(self.__class__), debug=debug)

    def __getattribute__(self, name):
        """
        if an asynchronous function is called and _next_call_blocking is set to true
        return a blocking lambda function that uses asyncio.run the called coroutine

        if an asynchronous function is called and _setup_task is pending return
        a coroutine that awaits the setup task before running
        """
        if asyncio.iscoroutinefunction(object.__getattribute__(self, name)):
            if object.__getattribute__(self, '_next_call_blocking'):
                def return_func(*args, **kwargs):
                    return asyncio.run(object.__getattribute__(self, name)(*args, **kwargs))

                self._next_call_blocking = False
                return return_func
            elif object.__getattribute__(self, '_setup_task') is not None:
                async def return_coro(*args, **kwargs):
                    await object.__getattribute__(self, '_setup_task')
                    self._setup_task = None
                    return await object.__getattribute__(self, name)(*args, **kwargs)

                return return_coro

        return object.__getattribute__(self, name)

    def blocking(self):
        """
        returns instance of self, which will perform next call to an async function with asyncio.run()
        """
        self._next_call_blocking = True
        return self

    @staticmethod
    def get_condition(record: Record, logical_operator='AND'):
        conditions = []

        for attr_name, attr_value in record.to_db().__dict__.items():
            if attr_value is not None:
                conditions.append(attr_name + '=' + str(attr_value))

        return f" {logical_operator} ".join(conditions)

    def _row_tuple_to_dict(self, row: tuple) -> dict:
        # cls.schema is set in db_setup.setup and is always in compliance with db column order
        return {column_name: row[0][i] for i, column_name in enumerate(self.schema.keys())}

    async def remove_record(self, record: Record) -> None:
        condition = self.get_condition(record)
        query = f"DELETE FROM {self.table_name} WHERE {condition}"
        await DBTools.runSql(query)

    async def select(self, record: Record) -> list[Record]:
        condition = self.get_condition(record)
        columns = " ,".join(self.schema.keys())
        query = f"SELECT ({columns}) FROM {self.table_name} WHERE {condition}"
        return [self.Record(**self._row_tuple_to_dict(row)).from_db() for row in await DBTools.runSql(query)]

    async def _select_all(self) -> list[Record]:
        columns = " ,".join(self.schema.keys())
        query = f"SELECT ({columns}) FROM {self.table_name}"
        return [self.Record(**self._row_tuple_to_dict(row)).from_db() for row in await DBTools.runSql(query)]

    async def insert(self, record: Record) -> None:
        column_names = []
        values = []

        for attr_name, attr_value in record.to_db().__dict__.items():
            if attr_value is not None:
                column_names.append(attr_name)

                if isinstance(attr_value, datetime.datetime):
                    values.append("'" + attr_value.strftime('%Y-%m-%d %H:%M:%S.%f') + "'")
                else:
                    values.append(str(attr_value))

        query = f"INSERT INTO {self.table_name} ({', '.join(column_names)}) VALUES ({', '.join(values)})"
        await DBTools.runSql(query)

