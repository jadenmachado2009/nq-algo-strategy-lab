import sys
import unittest
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cbe  # noqa: E402
from risk import RiskGuard  # noqa: E402

NY = ZoneInfo("America/New_York")


def flat(n, px=100.0):
    """n doji-ish bars with a 1-point range, so ATR ~= 1."""
    return [cbe.Bar(px, px + 0.5, px - 0.5, px) for _ in range(n)]


class TestSignal(unittest.TestCase):
    def test_shrinking_bearish_run_fades_long(self):
        bars = flat(20) + [cbe.Bar(100, 100.2, 98.9, 99.0),   # body 1.0
                           cbe.Bar(99.0, 99.1, 98.3, 98.4),    # body 0.6
                           cbe.Bar(98.4, 98.5, 98.0, 98.1)]    # body 0.3
        direction, atr = cbe.signal(bars, seq_len=3, atr_len=14, min_body_atr=0.1)
        self.assertEqual(direction, 1)
        self.assertGreater(atr, 0)

    def test_shrinking_bullish_run_fades_short(self):
        bars = flat(20) + [cbe.Bar(100, 101.1, 99.9, 101.0),
                           cbe.Bar(101.0, 101.7, 100.9, 101.6),
                           cbe.Bar(101.6, 102.0, 101.5, 101.9)]
        self.assertEqual(cbe.signal(bars, 3, 14, 0.1)[0], -1)

    def test_growing_bodies_no_signal(self):
        bars = flat(20) + [cbe.Bar(100, 100.1, 99.6, 99.7),
                           cbe.Bar(99.7, 99.8, 99.0, 99.1),
                           cbe.Bar(99.1, 99.2, 98.0, 98.1)]
        self.assertEqual(cbe.signal(bars, 3, 14, 0.1)[0], 0)

    def test_mixed_direction_no_signal(self):
        bars = flat(20) + [cbe.Bar(100, 100.1, 98.9, 99.0),
                           cbe.Bar(99.0, 99.7, 98.9, 99.6),
                           cbe.Bar(99.6, 99.7, 99.3, 99.4)]
        self.assertEqual(cbe.signal(bars, 3, 14, 0.1)[0], 0)

    def test_first_body_too_small_no_signal(self):
        bars = flat(20) + [cbe.Bar(100, 100.1, 99.9, 99.95),
                           cbe.Bar(99.95, 100, 99.9, 99.92),
                           cbe.Bar(99.92, 99.95, 99.9, 99.91)]
        self.assertEqual(cbe.signal(bars, 3, 14, min_body_atr=0.5)[0], 0)

    def test_seq_len_is_a_real_length(self):
        # 4 shrinking candles: seq_len=4 fires; a growing 4th-from-last breaks it.
        run = [cbe.Bar(100, 100, 98.5, 98.6), cbe.Bar(98.6, 98.6, 97.5, 97.6),
               cbe.Bar(97.6, 97.6, 96.9, 97.0), cbe.Bar(97.0, 97.0, 96.6, 96.7)]
        self.assertEqual(cbe.signal(flat(20) + run, 4, 14, 0.1)[0], 1)
        broken = [cbe.Bar(100, 100, 99.6, 99.7)] + run[1:]
        self.assertEqual(cbe.signal(flat(20) + broken, 4, 14, 0.1)[0], 0)

    def test_not_enough_bars(self):
        self.assertEqual(cbe.signal(flat(5), 3, 14, 0.1), (0, None))

    def test_wilder_atr_constant_range(self):
        self.assertAlmostEqual(cbe.wilder_atr(flat(30), 14), 1.0)


class TestSizing(unittest.TestCase):
    def test_mnq_sizing(self):
        # $50k * 1% = $500 risk; 25pt stop * $2 = $50/contract -> 10, capped at 5
        self.assertEqual(cbe.position_size(50_000, 0.01, 25, 2, 5), 5)
        self.assertEqual(cbe.position_size(50_000, 0.01, 100, 2, 5), 2)
        self.assertEqual(cbe.position_size(50_000, 0.01, 300, 2, 5), 0)
        self.assertEqual(cbe.position_size(50_000, 0.01, 0, 2, 5), 0)

    def test_round_tick(self):
        self.assertEqual(cbe.round_tick(17.13, 0.25), 17.25)
        self.assertEqual(cbe.round_tick(17.10, 0.25), 17.0)


class TestRiskGuard(unittest.TestCase):
    def guard(self):
        return RiskGuard(1000, 2, time(9, 30), time(11, 30), time(15, 50))

    def at(self, h, m, day=16):   # 2026-09-16 is a Wednesday
        return datetime(2026, 9, day, h, m, tzinfo=NY)

    def test_entry_window(self):
        g = self.guard()
        self.assertIsNone(g.can_enter(self.at(10, 0), True, False))
        self.assertIsNotNone(g.can_enter(self.at(9, 0), True, False))
        self.assertIsNotNone(g.can_enter(self.at(12, 0), True, False))
        self.assertIsNotNone(g.can_enter(self.at(10, 0, day=19), True, False))  # Saturday

    def test_one_position_at_a_time(self):
        g = self.guard()
        self.assertIsNotNone(g.can_enter(self.at(10, 0), False, False))
        self.assertIsNotNone(g.can_enter(self.at(10, 0), True, True))

    def test_max_trades_resets_next_day(self):
        g = self.guard()
        g.new_bar(self.at(10, 0))
        g.record_entry(); g.record_entry()
        self.assertIsNotNone(g.can_enter(self.at(10, 5), True, False))
        g.new_bar(self.at(10, 0, day=17))
        self.assertIsNone(g.can_enter(self.at(10, 0, day=17), True, False))

    def test_daily_loss_halts_until_next_day(self):
        g = self.guard()
        self.assertIsNotNone(g.must_flatten(self.at(10, 0), -1000))
        self.assertIsNotNone(g.can_enter(self.at(10, 30), True, False))
        self.assertIsNone(g.can_enter(self.at(10, 30, day=17), True, False))

    def test_flatten_time_and_kill(self):
        g = self.guard()
        self.assertIsNone(g.must_flatten(self.at(15, 0), -100))
        self.assertIsNotNone(g.must_flatten(self.at(15, 50), 0))
        g.killed = True
        self.assertIsNotNone(g.must_flatten(self.at(10, 0), None))
        self.assertIsNotNone(g.can_enter(self.at(10, 0), True, False))


if __name__ == "__main__":
    unittest.main()
