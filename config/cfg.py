import json

# !!!todo в конфиге написано говно рублевое
class config:
    _instance = None

    @classmethod
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = object.__new__(cls)

        return cls._instance

    def __init__(self):
        with open('config/config.json') as file:
            self.cfg = json.load(file)

    def __getitem__(self, item):
        return self.cfg[item]

    def this(self):
        """
        Returns
        local config of a __main__ file
        """
        import inspect
        import pathlib
        import os

        cfg_path = os.path.normpath(pathlib.Path(__file__).parent.resolve())
        cfg_path_list = cfg_path.split(os.sep)

        caller_path = inspect.stack()[1].filename
        caller_path_list = caller_path.split(os.sep)

        common_prefix_index = 0

        while caller_path_list[common_prefix_index] == cfg_path_list[common_prefix_index]:
            common_prefix_index += 1

        meaningful_caller_path = caller_path_list[common_prefix_index:]

        result = self

        for path_part in meaningful_caller_path:
            result = result[path_part.split('.')[0]]

        return result
