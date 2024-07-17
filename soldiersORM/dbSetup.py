from soldiersORM.DBTools import DBTools


class NoPermissionException(Exception):
    pass


def ask_permission(message: str):
    if input(f'perform this action: {message}? Y/N').lower() != 'y':
        raise NoPermissionException


async def _check_table_exists(table_name: str) -> bool:
    sql = f"SELECT EXISTS (SELECT FROM pg_tables WHERE tablename = '{table_name}');"
    res = await DBTools.runSql(sql)
    return res[0][0]


async def _create_table(table_name: str, schema: dict[str, type]):
    columns = [' '.join((name, DBTools.python_to_db[data_type])) for name, data_type in schema.items()]
    sql = f"CREATE TABLE {table_name} ({', '.join(columns)});"
    await DBTools.runSql(sql)


async def _drop_column(table_name: str, column_name: str):
    sql = f"ALTER TABLE {table_name} DROP COLUMN {column_name};"
    ask_permission(sql)
    await DBTools.runSql(sql)


async def _change_column_type(table_name: str, column_name: str, new_type: type):
    sql = f"ALTER TABLE {table_name} ALTER COLUMN {column_name} TYPE {DBTools.python_to_db[new_type]};"
    ask_permission(sql)
    await DBTools.runSql(sql)


async def _add_column(table_name: str, column_name: str, new_type: type):
    sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {DBTools.python_to_db[new_type]};"
    await DBTools.runSql(sql)


async def _get_schema(table_name: str) -> dict[str, type]:
    sql = f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table_name}';"
    db_types_schema = (await DBTools().runSql(sql))
    python_types_schema = {row[0]: DBTools.db_to_python[row[1]] for row in db_types_schema}
    return python_types_schema


def _get_all_children(cls: type) -> list[type]:
    """
    dfs-style
    returns a list of all children a class has
    """
    res = []
    children = cls.__subclasses__()
    res.extend(children)

    for child in children:
        res.extend(_get_all_children(child))

    return res


async def setup(cls: type):
    children: list[type] = _get_all_children(cls)

    # if setup is not called from OrmBase
    if cls.table_name is not None:
        children.append(cls)

    for child in children:
        child_dataclass_schema = {}

        for key, val in child.Record.__annotations__.items():
            if isinstance(key, str) and isinstance(val, type):
                child_dataclass_schema[key] = val

        if not await _check_table_exists(child.table_name):
            await _create_table(child.table_name, child_dataclass_schema)
            child.schema = child_dataclass_schema
            continue

        child_table_schema = await _get_schema(child.table_name)

        for name, data_type in child_table_schema.items():
            if name not in child_dataclass_schema:
                await _drop_column(child.table_name, name)

            if data_type is not child_dataclass_schema[name]:
                await _change_column_type(child.table_name, name, child_dataclass_schema[name])

        for name, data_type in child_dataclass_schema.items():
            if name not in child_table_schema:
                await _add_column(child.table_name, name, data_type)

        ordered_schema = await _get_schema(child.table_name)
        child.schema = ordered_schema
        child.is_initialized = True
