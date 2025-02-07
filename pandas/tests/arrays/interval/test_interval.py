import operator

import numpy as np
import pytest

from pandas.core.dtypes.common import is_list_like

import pandas as pd
from pandas import (
    Categorical,
    Index,
    Interval,
    IntervalIndex,
    Period,
    Series,
    Timedelta,
    Timestamp,
    date_range,
    period_range,
    timedelta_range,
)
import pandas._testing as tm
from pandas.core.arrays import IntervalArray


@pytest.fixture(
    params=[
        (Index([0, 2, 4]), Index([1, 3, 5])),
        (Index([0.0, 1.0, 2.0]), Index([1.0, 2.0, 3.0])),
        (timedelta_range("0 days", periods=3), timedelta_range("1 day", periods=3)),
        (date_range("20170101", periods=3), date_range("20170102", periods=3)),
        (
            date_range("20170101", periods=3, tz="US/Eastern"),
            date_range("20170102", periods=3, tz="US/Eastern"),
        ),
    ],
    ids=lambda x: str(x[0].dtype),
)
def left_right_dtypes(request):
    """
    Fixture for building an IntervalArray from various dtypes
    """
    return request.param


def create_categorical_intervals(left, right, closed="right"):
    return Categorical(IntervalIndex.from_arrays(left, right, closed))


def create_series_intervals(left, right, closed="right"):
    return Series(IntervalArray.from_arrays(left, right, closed))


def create_series_categorical_intervals(left, right, closed="right"):
    return Series(Categorical(IntervalIndex.from_arrays(left, right, closed)))


class TestAttributes:
    @pytest.mark.parametrize(
        "left, right",
        [
            (0, 1),
            (Timedelta("0 days"), Timedelta("1 day")),
            (Timestamp("2018-01-01"), Timestamp("2018-01-02")),
            (
                Timestamp("2018-01-01", tz="US/Eastern"),
                Timestamp("2018-01-02", tz="US/Eastern"),
            ),
        ],
    )
    @pytest.mark.parametrize("constructor", [IntervalArray, IntervalIndex])
    def test_is_empty(self, constructor, left, right, closed):
        # GH27219
        tuples = [(left, left), (left, right), np.nan]
        expected = np.array([closed != "both", False, False])
        result = constructor.from_tuples(tuples, closed=closed).is_empty
        tm.assert_numpy_array_equal(result, expected)


class TestMethods:
    @pytest.mark.parametrize("new_closed", ["left", "right", "both", "neither"])
    def test_set_closed(self, closed, new_closed):
        # GH 21670
        array = IntervalArray.from_breaks(range(10), closed=closed)
        result = array.set_closed(new_closed)
        expected = IntervalArray.from_breaks(range(10), closed=new_closed)
        tm.assert_extension_array_equal(result, expected)

    @pytest.mark.parametrize(
        "other",
        [
            Interval(0, 1, closed="right"),
            IntervalArray.from_breaks([1, 2, 3, 4], closed="right"),
        ],
    )
    def test_where_raises(self, other):
        ser = pd.Series(IntervalArray.from_breaks([1, 2, 3, 4], closed="left"))
        match = "'value.closed' is 'right', expected 'left'."
        with pytest.raises(ValueError, match=match):
            ser.where([True, False, True], other=other)


class TestSetitem:
    def test_set_na(self, left_right_dtypes):
        left, right = left_right_dtypes
        result = IntervalArray.from_arrays(left, right)
        result[0] = np.nan

        expected_left = Index([left._na_value] + list(left[1:]))
        expected_right = Index([right._na_value] + list(right[1:]))
        expected = IntervalArray.from_arrays(expected_left, expected_right)

        tm.assert_extension_array_equal(result, expected)


class TestComparison:
    @pytest.fixture(params=[operator.eq, operator.ne])
    def op(self, request):
        return request.param

    @pytest.fixture
    def array(self, left_right_dtypes):
        """
        Fixture to generate an IntervalArray of various dtypes containing NA if possible
        """
        left, right = left_right_dtypes
        if left.dtype != "int64":
            left, right = left.insert(4, np.nan), right.insert(4, np.nan)
        else:
            left, right = left.insert(4, 10), right.insert(4, 20)
        return IntervalArray.from_arrays(left, right)

    @pytest.fixture(
        params=[
            IntervalArray.from_arrays,
            IntervalIndex.from_arrays,
            create_categorical_intervals,
            create_series_intervals,
            create_series_categorical_intervals,
        ],
        ids=[
            "IntervalArray",
            "IntervalIndex",
            "Categorical[Interval]",
            "Series[Interval]",
            "Series[Categorical[Interval]]",
        ],
    )
    def interval_constructor(self, request):
        """
        Fixture for all pandas native interval constructors.
        To be used as the LHS of IntervalArray comparisons.
        """
        return request.param

    def elementwise_comparison(self, op, array, other):
        """
        Helper that performs elementwise comparisions between `array` and `other`
        """
        other = other if is_list_like(other) else [other] * len(array)
        return np.array([op(x, y) for x, y in zip(array, other)])

    def test_compare_scalar_interval(self, op, array):
        # matches first interval
        other = array[0]
        result = op(array, other)
        expected = self.elementwise_comparison(op, array, other)
        tm.assert_numpy_array_equal(result, expected)

        # matches on a single endpoint but not both
        other = Interval(array.left[0], array.right[1])
        result = op(array, other)
        expected = self.elementwise_comparison(op, array, other)
        tm.assert_numpy_array_equal(result, expected)

    def test_compare_scalar_interval_mixed_closed(self, op, closed, other_closed):
        array = IntervalArray.from_arrays(range(2), range(1, 3), closed=closed)
        other = Interval(0, 1, closed=other_closed)

        result = op(array, other)
        expected = self.elementwise_comparison(op, array, other)
        tm.assert_numpy_array_equal(result, expected)

    def test_compare_scalar_na(self, op, array, nulls_fixture):
        result = op(array, nulls_fixture)
        expected = self.elementwise_comparison(op, array, nulls_fixture)
        tm.assert_numpy_array_equal(result, expected)

    @pytest.mark.parametrize(
        "other",
        [
            0,
            1.0,
            True,
            "foo",
            Timestamp("2017-01-01"),
            Timestamp("2017-01-01", tz="US/Eastern"),
            Timedelta("0 days"),
            Period("2017-01-01", "D"),
        ],
    )
    def test_compare_scalar_other(self, op, array, other):
        result = op(array, other)
        expected = self.elementwise_comparison(op, array, other)
        tm.assert_numpy_array_equal(result, expected)

    def test_compare_list_like_interval(
        self, op, array, interval_constructor,
    ):
        # same endpoints
        other = interval_constructor(array.left, array.right)
        result = op(array, other)
        expected = self.elementwise_comparison(op, array, other)
        tm.assert_numpy_array_equal(result, expected)

        # different endpoints
        other = interval_constructor(array.left[::-1], array.right[::-1])
        result = op(array, other)
        expected = self.elementwise_comparison(op, array, other)
        tm.assert_numpy_array_equal(result, expected)

        # all nan endpoints
        other = interval_constructor([np.nan] * 4, [np.nan] * 4)
        result = op(array, other)
        expected = self.elementwise_comparison(op, array, other)
        tm.assert_numpy_array_equal(result, expected)

    def test_compare_list_like_interval_mixed_closed(
        self, op, interval_constructor, closed, other_closed
    ):
        array = IntervalArray.from_arrays(range(2), range(1, 3), closed=closed)
        other = interval_constructor(range(2), range(1, 3), closed=other_closed)

        result = op(array, other)
        expected = self.elementwise_comparison(op, array, other)
        tm.assert_numpy_array_equal(result, expected)

    @pytest.mark.parametrize(
        "other",
        [
            (
                Interval(0, 1),
                Interval(Timedelta("1 day"), Timedelta("2 days")),
                Interval(4, 5, "both"),
                Interval(10, 20, "neither"),
            ),
            (0, 1.5, Timestamp("20170103"), np.nan),
            (
                Timestamp("20170102", tz="US/Eastern"),
                Timedelta("2 days"),
                "baz",
                pd.NaT,
            ),
        ],
    )
    def test_compare_list_like_object(self, op, array, other):
        result = op(array, other)
        expected = self.elementwise_comparison(op, array, other)
        tm.assert_numpy_array_equal(result, expected)

    def test_compare_list_like_nan(self, op, array, nulls_fixture):
        other = [nulls_fixture] * 4
        result = op(array, other)
        expected = self.elementwise_comparison(op, array, other)
        tm.assert_numpy_array_equal(result, expected)

    @pytest.mark.parametrize(
        "other",
        [
            np.arange(4, dtype="int64"),
            np.arange(4, dtype="float64"),
            date_range("2017-01-01", periods=4),
            date_range("2017-01-01", periods=4, tz="US/Eastern"),
            timedelta_range("0 days", periods=4),
            period_range("2017-01-01", periods=4, freq="D"),
            Categorical(list("abab")),
            Categorical(date_range("2017-01-01", periods=4)),
            pd.array(list("abcd")),
            pd.array(["foo", 3.14, None, object()]),
        ],
        ids=lambda x: str(x.dtype),
    )
    def test_compare_list_like_other(self, op, array, other):
        result = op(array, other)
        expected = self.elementwise_comparison(op, array, other)
        tm.assert_numpy_array_equal(result, expected)

    @pytest.mark.parametrize("length", [1, 3, 5])
    @pytest.mark.parametrize("other_constructor", [IntervalArray, list])
    def test_compare_length_mismatch_errors(self, op, other_constructor, length):
        array = IntervalArray.from_arrays(range(4), range(1, 5))
        other = other_constructor([Interval(0, 1)] * length)
        with pytest.raises(ValueError, match="Lengths must match to compare"):
            op(array, other)

    @pytest.mark.parametrize(
        "constructor, expected_type, assert_func",
        [
            (IntervalIndex, np.array, tm.assert_numpy_array_equal),
            (Series, Series, tm.assert_series_equal),
        ],
    )
    def test_index_series_compat(self, op, constructor, expected_type, assert_func):
        # IntervalIndex/Series that rely on IntervalArray for comparisons
        breaks = range(4)
        index = constructor(IntervalIndex.from_breaks(breaks))

        # scalar comparisons
        other = index[0]
        result = op(index, other)
        expected = expected_type(self.elementwise_comparison(op, index, other))
        assert_func(result, expected)

        other = breaks[0]
        result = op(index, other)
        expected = expected_type(self.elementwise_comparison(op, index, other))
        assert_func(result, expected)

        # list-like comparisons
        other = IntervalArray.from_breaks(breaks)
        result = op(index, other)
        expected = expected_type(self.elementwise_comparison(op, index, other))
        assert_func(result, expected)

        other = [index[0], breaks[0], "foo"]
        result = op(index, other)
        expected = expected_type(self.elementwise_comparison(op, index, other))
        assert_func(result, expected)


def test_repr():
    # GH 25022
    arr = IntervalArray.from_tuples([(0, 1), (1, 2)])
    result = repr(arr)
    expected = (
        "<IntervalArray>\n"
        "[(0, 1], (1, 2]]\n"
        "Length: 2, closed: right, dtype: interval[int64]"
    )
    assert result == expected
