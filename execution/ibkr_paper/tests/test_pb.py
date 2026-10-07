import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pb_engine as pb  # noqa: E402

NY = ZoneInfo("America/New_York")
T0 = datetime(2026, 9, 16, 4, 0, tzinfo=NY)   # well before the session


def bar(i, o, h, l, c):
    return pb.Bar(T0 + timedelta(minutes=5 * i), o, h, l, c)


def flat(n, px=100.0, start=0):
    return [bar(start + i, px, px + 0.5, px - 0.5, px) for i in range(n)]


class TestFVG(unittest.TestCase):
    def test_finds_bullish_gap(self):
        bars = flat(5) + [bar(5, 100, 100.5, 99.5, 100), bar(6, 100, 105, 100, 104), bar(7, 104, 106, 102, 105)]
        z = pb.latest_fvg(bars, bullish=True, lookback=10)
        self.assertIsNotNone(z)
        self.assertEqual((z.top, z.bot), (102, 100.5))

    def test_takes_most_recent_gap_not_the_oldest(self):
        """Audit fix 2: the Pine version latched onto the first gap it found."""
        bars = (flat(3)
                + [bar(3, 100, 100.5, 99.5, 100), bar(4, 100, 110, 100, 109), bar(5, 109, 111, 107, 110)]  # old gap 100.5-107
                + flat(5, px=120, start=6)
                + [bar(11, 120, 120.5, 119.5, 120), bar(12, 120, 130, 120, 129), bar(13, 129, 131, 127, 130)])  # new gap
        z = pb.latest_fvg(bars, bullish=True, lookback=20)
        self.assertEqual((z.top, z.bot), (127, 120.5), "should return the newest gap")

    def test_lookback_excludes_stale_gap(self):
        bars = ([bar(0, 100, 100.5, 99.5, 100), bar(1, 100, 110, 100, 109), bar(2, 109, 111, 107, 110)]
                + flat(30, px=120, start=3))
        self.assertIsNone(pb.latest_fvg(bars, bullish=True, lookback=10))
        self.assertIsNotNone(pb.latest_fvg(bars, bullish=True, lookback=40))


class TestSweep(unittest.TestCase):
    def test_sweep_detected_when_low_undercuts_and_closes_back(self):
        bars = flat(12) + [bar(12, 100, 100.2, 98.0, 100.1)]     # dips below 99.5, closes above
        self.assertTrue(pb.swept(bars, long=True, lookback=5, swing_len=10))

    def test_no_sweep_when_close_stays_below(self):
        bars = flat(12) + [bar(12, 100, 100.2, 98.0, 98.2)]      # breaks down and stays
        self.assertFalse(pb.swept(bars, long=True, lookback=5, swing_len=10))

    def test_old_sweep_falls_out_of_lookback(self):
        bars = flat(12) + [bar(12, 100, 100.2, 98.0, 100.1)] + flat(8, start=13)
        self.assertFalse(pb.swept(bars, long=True, lookback=5, swing_len=10))
        self.assertTrue(pb.swept(bars, long=True, lookback=20, swing_len=10))

    def test_short_side(self):
        bars = flat(12) + [bar(12, 100, 102.0, 99.8, 99.9)]
        self.assertTrue(pb.swept(bars, long=False, lookback=5, swing_len=10))
        self.assertFalse(pb.swept(bars, long=True, lookback=5, swing_len=10))


class TestEngine(unittest.TestCase):
    def feed(self, engine, bars):
        out = [engine.on_bar(b) for b in bars]
        return [s for s in out if s]

    def test_no_signal_outside_session(self):
        e = pb.PBEngine()
        # T0 is 04:00 NY — before the 08:30 window
        self.assertEqual(self.feed(e, flat(60)), [])

    def test_zone_expires(self):
        e = pb.PBEngine(fvg_max_age=3)
        bars = flat(3) + [bar(3, 100, 100.5, 99.5, 100), bar(4, 100, 105, 100, 104), bar(5, 104, 106, 102, 105)]
        self.feed(e, bars)
        self.assertIsNotNone(e.bull5)
        self.feed(e, flat(5, px=104, start=6))
        self.assertIsNone(e.bull5, "stale zone should expire")

    def _walk(self, seed=7, n=4000):
        import random
        random.seed(seed)
        px, bars = 20000.0, []
        for i in range(n):
            o = px
            px += random.gauss(0, 8)
            h, l = max(o, px) + abs(random.gauss(0, 3)), min(o, px) - abs(random.gauss(0, 3))
            bars.append(bar(i, o, h, l, px))
        return bars

    def test_sweep_filter_actually_removes_trades(self):
        """Audit fix 1: in the Pine version the sweep was computed but never
        applied, so it could not change the trade list. Here it must."""
        bars = self._walk()
        with_sweep = len(self.feed(pb.PBEngine(), bars))
        without = len(self.feed(pb.PBEngine(sweep_lookback=10_000, swing_len=2), bars))
        self.assertGreater(without, with_sweep, "loosening the sweep filter must admit more trades")

    def test_ifvg_age_limit_is_enforced(self):
        """Audit fix 2: the Pine detector latched onto one gap forever. The
        inversion must stop counting once the gap is older than the limit."""
        # bearish gap at bars 3-5 (high[5]=97 < low[3]=99.5), then drift up through it
        seq = (flat(3)
               + [bar(3, 100, 100.5, 99.5, 100), bar(4, 99.5, 99.6, 96, 96.5), bar(5, 96.5, 97, 95, 96)]
               + [bar(6 + i, 96 + i, 97 + i, 95 + i, 96.5 + i) for i in range(12)])
        fresh = pb.PBEngine(ifvg_max_age=30)
        stale = pb.PBEngine(ifvg_max_age=2)
        for b in seq:
            fresh.on_bar(b)
            stale.on_bar(b)
        self.assertTrue(fresh._inverted(bullish=True), "recent inverted gap should count")
        self.assertFalse(stale._inverted(bullish=True), "gap older than the limit must not count")

    def test_engine_runs_over_random_walk_without_error(self):
        e = pb.PBEngine()
        signals = self.feed(e, self._walk(n=2000))
        for direction, sd, td in signals:
            self.assertIn(direction, (1, -1))
            self.assertGreater(sd, 0)
            self.assertAlmostEqual(td / sd, e.rr, places=6)


if __name__ == "__main__":
    unittest.main()
