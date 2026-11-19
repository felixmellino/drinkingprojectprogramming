"""run_parallel overlaps independent reads and keeps order and errors predictable."""
import time

import pytest

from parallel import run_parallel


def test_results_come_back_in_call_order_and_overlap_in_time():
    def slow(value):
        def call():
            time.sleep(0.2)
            return value
        return call
    start = time.perf_counter()
    assert run_parallel(slow('a'), slow('b'), slow('c')) == ['a', 'b', 'c']
    assert time.perf_counter() - start < 0.5          # about 0.2 s, not 0.6 s


def test_zero_or_one_call_needs_no_threads():
    assert run_parallel() == []
    assert run_parallel(lambda: 7) == [7]


def test_first_error_in_call_order_is_raised_after_all_calls_finished():
    done = []
    def good():
        time.sleep(0.1)
        done.append('good')
        return 1
    def bad():
        raise ValueError('boom')
    with pytest.raises(ValueError, match='boom'):
        run_parallel(good, bad)
    assert done == ['good']


def test_large_gallery_uses_a_bounded_worker_pool_and_keeps_display_order():
    import threading
    from parallel import MAX_READ_WORKERS
    lock=threading.Lock()
    active=peak=0
    def read(index):
        nonlocal active,peak
        with lock:
            active+=1
            peak=max(peak,active)
        time.sleep(0.01)
        with lock:
            active-=1
        return index
    assert run_parallel(*[lambda i=i:read(i) for i in range(25)])==list(range(25))
    assert 1<peak<=MAX_READ_WORKERS
