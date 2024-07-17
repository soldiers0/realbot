import time

from typing_extensions import Self
from typing import Callable
from dataLayer.CsmFloatOverpayRecords import CsmFloatOverpayRecords
from dataLayer.CsmPatternOverpayRecords import CsmPatternOverpayRecords
from dataLayer.ItemsInfoRepository import ItemsInfoRepository
from models import Deal
from config.cfg import config
from tools.itemTools import getFloatRangeFromCondition
from scipy.optimize import curve_fit
from matplotlib import pyplot as plt
import numpy as np


class NotDefinedError(NotImplementedError):
    pass


profit_threshold = config()['mainParser']["min_relative_profit"]


class FloatCurve:
    class NotEnoughDataPointsError(Exception):
        def __init__(self, item_name):
            super().__init__(f'not enough data points to approximate the overpay curve for - {item_name}')


    class AbstractOverpayPredictor:
        @staticmethod
        def __call__(x: float):
            return 0

        @staticmethod
        def antiderivative(x: float):
            return 0

        @staticmethod
        def get_threshold_overpay_point():
            return 0

    class fitted_linear(AbstractOverpayPredictor):
        def __init__(self, params, float_range):
            self.params = params
            self.float_range = float_range

        def __call__(self, x: float):
            return max(0, self.params[0] + x * self.params[1])

        def antiderivative(self, x: float):
            return x * self.params[0] + (x ** 2) * (self.params[1] / 2)

        def get_threshold_overpay_point(self):
            point = (profit_threshold - self.params[0]) / self.params[1]

            # inverted float profit threshold unreachable
            if point > self.float_range[1]:
                return self.float_range[1]

            # profit threshold unreachable
            if point < self.float_range[0]:
                return self.float_range[0]

            return point

    class fitted_quadratic(AbstractOverpayPredictor):
        def __init__(self, params: list[float], float_curve_obj: 'FloatCurve', x_plain: list[float], y_plain: list[float]):
            if float_curve_obj.inverted_float:
                # find a point at which profit is better than min profit in the config
                ind = -1

                for i in range(len(x_plain)):
                    if y_plain[i] >= profit_threshold:
                        ind = i
                        break

                if ind == -1:
                    self.left_border = float_curve_obj.item_float_range[1]
                else:
                    self.left_border = x_plain[ind]
                self.right_border = float_curve_obj.item_float_range[1]
            else:
                self.left_border = float_curve_obj.item_float_range[0]

                # find a point at which profit is better than min profit in the config
                ind = -1

                for i in range(len(x_plain) - 1, -1, -1):
                    if y_plain[i] > profit_threshold:
                        ind = i

                if ind == -1:
                    self.right_border = float_curve_obj.item_float_range[0]
                else:
                    self.right_border = x_plain[ind]

            self.params = params
            self.inverted_float = float_curve_obj.inverted_float

        def __call__(self, x: float):
            return self.params[0] + x * self.params[1] + (x ** 2) * self.params[2] \
                if self.left_border <= x <= self.right_border else 0

        def antiderivative(self, x: float):
            # quadratic integral should not be evaluated outside of the valid range,
            # because of function's parabolic shape
            if not self.left_border <= x <= self.right_border:
                raise ValueError

            return x * self.params[0] + (x ** 2) * self.params[1] / 2 + (x ** 3) * self.params[2] / 3

        def get_threshold_overpay_point(self):
            if self.inverted_float:
                return self.left_border

            return self.right_border

    class fitted_constant(AbstractOverpayPredictor):
        def __init__(self, val: float, float_curve_obj: 'FloatCurve', x_plain: list[float]):
            inverted_float = abs(float_curve_obj.item_float_range[0] - x_plain[-1]) > \
                             abs(float_curve_obj.item_float_range[1] - x_plain[-1])

            if inverted_float:
                if val > profit_threshold:
                    self.left_border = x_plain[0]
                else:
                    self.left_border = float_curve_obj.item_float_range[1]

                self.right_border = float_curve_obj.item_float_range[1]
            else:
                self.left_border = float_curve_obj.item_float_range[0]

                if val > profit_threshold:
                    self.right_border = x_plain[-1]
                else:
                    self.right_border = float_curve_obj.item_float_range[0]

            self.inverted_float = float_curve_obj.inverted_float
            self.val = val

        def __call__(self, x: float):
            return self.val if self.left_border <= x <= self.right_border else 0

        def get_threshold_overpay_point(self):
            if self.inverted_float:
                return self.left_border

            return self.right_border

    _cache = {}

    def __init__(
            self,
            records: list[tuple[float, float]] | list[CsmFloatOverpayRecords.Record],
            item_name: str,
            skin_float_range: tuple[float, float] | list[float, float]
    ):
        """
        If the curve can't be initiated AttributeError is raised
        """
        if len(records) < 3:
            raise self.NotEnoughDataPointsError(item_name)

        records.sort(key=lambda x: x.item_float if isinstance(x, CsmFloatOverpayRecords.Record) else x[0])

        x_plain = [x.item_float if isinstance(x, CsmFloatOverpayRecords.Record) else x[0] for x in records]
        y_plain = [x.overpay if isinstance(x, CsmFloatOverpayRecords.Record) else x[1] for x in records]

        self.inverted_float = y_plain[0] < y_plain[-1]
        self.item_name = item_name

        quality = '(' + self.item_name.split(' (')[-1]
        quality_float_range = getFloatRangeFromCondition(quality)
        self.item_float_range = (max(skin_float_range[0], quality_float_range[0]), min(skin_float_range[1],
                                 quality_float_range[1]))

        # overpay is constant
        if y_plain[0] == y_plain[-1]:
            self.predict = self.fitted_constant(y_plain[0], self, x_plain)
            return

        def linear(x, p0, p1):
            return p0 + p1 * x

        def quadratic(x, p0, p1, p2):
            return p0 + p1 * x + p2 * (x ** 2)

        params_l, _ = curve_fit(linear, x_plain, y_plain)

        # curve_fit won't work if the number of data points is lower tha the number of parameters
        if len(x_plain) == 2:
            self.predict = self.fitted_linear(params_l, self.item_float_range)
            self._cache[self.item_name] = (self, time.time())
            return

        params_q, _ = curve_fit(quadratic, x_plain, y_plain)

        def sse(func: Callable):
            sum_ = 0

            for x, y in zip(x_plain, y_plain):
                sum_ += (func(x) - y) ** 2

            return sum_

        f_q = self.fitted_quadratic(params_q, self, x_plain, y_plain)
        f_l = self.fitted_linear(params_l, self.item_float_range)

        if sse(f_l) > sse(f_q):
            self.predict = f_q
        else:
            self.predict = f_l

        self._cache[self.item_name] = (self, time.time())

    def predict(self, item_float: float) -> float:
        raise NotDefinedError

    def get_overpay_expectancy(self) -> float:
        if isinstance(self.predict, self.fitted_constant):
            # overpay_range / item_float_range * constant
            return (self.predict.right_border - self.predict.left_border) / \
                   (self.item_float_range[1] - self.item_float_range[0]) * \
                   self.predict.val

        antiderivative = self.predict.antiderivative
        zero_overpay_float = self.predict.get_threshold_overpay_point()

        if self.inverted_float:
            area_under_graph = antiderivative(self.item_float_range[1]) - antiderivative(zero_overpay_float)
        else:
            area_under_graph = abs(antiderivative(zero_overpay_float) - antiderivative(self.item_float_range[0]))

        return area_under_graph / (self.item_float_range[1] - self.item_float_range[0])

    def get_deal_p(self) -> float:
        """
        return the probability that a random item's overpay is going to exceed the profit threshold
        """
        zero_overpay_float = self.predict.get_threshold_overpay_point()

        if self.inverted_float:
            profit_segment = self.item_float_range[1] - zero_overpay_float
        else:
            profit_segment = zero_overpay_float - self.item_float_range[0]

        return profit_segment / (self.item_float_range[1] - self.item_float_range[0])

    def plot(self):
        x = np.linspace(*self.item_float_range)
        y = np.array([self.predict(x0) for x0 in x])
        plt.plot(x, y, label=self.item_name)
        plt.legend(loc='upper left')
        plt.show()

    @classmethod
    async def load_curve(cls, item_name: str, force_cache=False) -> Self:
        day = 60 * 60 * 24

        if item_name in cls._cache and cls._cache[item_name][1] - time.time() < day:
            return cls._cache[item_name][0]

        #  if force_cache is True no db query should be performed
        if force_cache:
            raise FloatCurve.NotEnoughDataPointsError

        item_record = await ItemsInfoRepository().get_item(item_name)

        condition = CsmFloatOverpayRecords.Record(item_name=item_name)

        float_range = (item_record.min_float, item_record.max_float)

        return cls(await CsmFloatOverpayRecords().select(condition), item_name, float_range)


class PatternOverpay:
    _cache = {}

    def __init__(self, records: list[tuple[int, float]] | list[CsmPatternOverpayRecords.Record], item_name: str):
        self.overpayInfo = [0.0] * 1001

        for record in records:
            if isinstance(record, CsmPatternOverpayRecords.Record):
                self.overpayInfo[record.pattern] = record.overpay
            else:
                self.overpayInfo[record[0]] = record[1]

        self.predict = lambda pattern: self.overpayInfo[pattern]

    def predict(self, item_pattern: int) -> float:
        raise NotDefinedError

    def get_overpay_expectancy(self):
        return sum(self.overpayInfo) / 1000

    @classmethod
    async def load_overpay_predictor(cls, item_name: str, force_cache=False) -> Self:
        day = 60 * 60 * 24

        if item_name in cls._cache and cls._cache[item_name][1] - time.time() < day:
            return cls._cache[item_name]

        #  if force_cache is True no db query should be performed
        if force_cache:
            return cls([], item_name)

        condition = CsmPatternOverpayRecords.Record(
            item_name=item_name
        )

        return cls(await CsmPatternOverpayRecords().select(condition), item_name)


async def predictProfit(*args: tuple[Deal] | tuple[float, int, str, str], force_cache=False) -> float:
    """
    either takes in a Deal object or a (float, pattern, stickers, name) tuple
    """
    if len(args) == 1:
        args: tuple[Deal]
        deal: Deal = args[0]
        overpay_predictor = await PatternOverpay.load_overpay_predictor(deal.itemName, force_cache=force_cache)
        pattern_overpay = overpay_predictor.predict(deal.pattern)
        float_curve = await FloatCurve.load_curve(deal.itemName, force_cache=force_cache)
        float_overpay = float_curve.predict(deal.itemFloat)
    else:
        args: tuple[float, int, str, str]
        float_val, pattern, stickers, item_name = args

        overpay_predictor = await PatternOverpay.load_overpay_predictor(item_name, force_cache=force_cache)
        pattern_overpay = overpay_predictor.predict(pattern)
        float_curve = await FloatCurve.load_curve(item_name, force_cache=force_cache)
        float_overpay = float_curve.predict(float_val)

    return float_overpay + pattern_overpay
