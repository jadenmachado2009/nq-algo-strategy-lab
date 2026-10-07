// CBE — Candle Body Exhaustion, NinjaTrader 8 port for MNQ.
// Same logic as quantconnect/cbe_mnq.py. Use it two ways:
//   1. Strategy Analyzer  -> backtest on NT historical data
//   2. Chart / Strategies tab on the Sim101 account -> free paper trading on live data
//
// Install: NinjaTrader > New > NinjaScript Editor > Strategies > right-click > New Strategy,
// name it CBE_MNQ, replace the whole file with this, press F5 to compile.
//
// Session times are in New York time and converted from your PC's time zone,
// so this works correctly from Singapore.

#region Using declarations
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using NinjaTrader.Cbi;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;
#endregion

namespace NinjaTrader.NinjaScript.Strategies
{
    public class CBE_MNQ : Strategy
    {
        private ATR atr;
        private TimeZoneInfo newYork;
        private double dayStartCumProfit;
        private DateTime currentNyDate = DateTime.MinValue;
        private bool haltedToday;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "CBE_MNQ";
                Description = "Candle Body Exhaustion — fade shrinking-body runs, ATR bracket, NY morning only.";
                Calculate = Calculate.OnBarClose;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 600;
                BarsRequiredToTrade = 20;
                StartBehavior = StartBehavior.WaitUntilFlat;
                RealtimeErrorHandling = RealtimeErrorHandling.StopCancelCloseIgnoreRejects;
                StopTargetHandling = StopTargetHandling.PerEntryExecution;
                IncludeCommission = true;
                Slippage = 1;

                SeqLen = 3;
                MinBodyAtr = 0.1;
                AtrLen = 14;
                AtrSL = 1.7;
                AtrTP = 2.5;

                AccountSize = 50000;
                RiskPercent = 1.0;
                MaxContracts = 10;
                MaxDailyLoss = 1000;

                SessionStartHHmm = 930;
                SessionEndHHmm = 1130;
                FlattenHHmm = 1550;
            }
            else if (State == State.Configure)
            {
                newYork = FindNewYorkZone();
            }
            else if (State == State.DataLoaded)
            {
                atr = ATR(AtrLen);
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < Math.Max(BarsRequiredToTrade, SeqLen + AtrLen))
                return;

            DateTime ny = TimeZoneInfo.ConvertTime(Time[0], Core.Globals.GeneralOptions.TimeZoneInfo, newYork);
            int hhmm = ny.Hour * 100 + ny.Minute;
            double cumProfit = SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit;

            // New NY trading day -> reset daily loss tracking
            if (ny.Date != currentNyDate)
            {
                currentNyDate = ny.Date;
                dayStartCumProfit = cumProfit;
                haltedToday = false;
            }

            // Daily loss limit (realized + open)
            double openPnl = Position.MarketPosition == MarketPosition.Flat
                ? 0
                : Position.GetUnrealizedProfitLoss(PerformanceUnit.Currency, Close[0]);
            if (!haltedToday && (cumProfit - dayStartCumProfit + openPnl) <= -MaxDailyLoss)
            {
                haltedToday = true;
                FlattenAll("DailyLoss");
                Print(string.Format("{0} daily loss limit hit — halted for the day", ny));
            }

            if (hhmm >= FlattenHHmm)
            {
                FlattenAll("TimeFlat");
                return;
            }

            if (haltedToday || Position.MarketPosition != MarketPosition.Flat)
                return;
            if (hhmm < SessionStartHHmm || hhmm > SessionEndHHmm)
                return;

            double atrNow = atr[0];
            int stopTicks = (int)Math.Round(atrNow * AtrSL / TickSize);
            int targetTicks = (int)Math.Round(atrNow * AtrTP / TickSize);
            if (stopTicks < 1)
                return;

            double riskPerContract = stopTicks * TickSize * Instrument.MasterInstrument.PointValue;
            int qty = Math.Min(MaxContracts, (int)Math.Floor(AccountSize * RiskPercent / 100.0 / riskPerContract));
            if (qty < 1)
                return;

            if (Shrinking(bearish: true, atrNow: atrNow))
            {
                SetStopLoss("CBE_L", CalculationMode.Ticks, stopTicks, false);
                SetProfitTarget("CBE_L", CalculationMode.Ticks, targetTicks);
                EnterLong(qty, "CBE_L");
            }
            else if (Shrinking(bearish: false, atrNow: atrNow))
            {
                SetStopLoss("CBE_S", CalculationMode.Ticks, stopTicks, false);
                SetProfitTarget("CBE_S", CalculationMode.Ticks, targetTicks);
                EnterShort(qty, "CBE_S");
            }
        }

        // SeqLen consecutive same-direction candles, bodies shrinking oldest -> newest,
        // first body >= MinBodyAtr * ATR. A real length, not an offset (see AUDIT.md).
        private bool Shrinking(bool bearish, double atrNow)
        {
            double prev = double.MaxValue;
            for (int i = SeqLen - 1; i >= 0; i--)
            {
                double body = bearish ? Open[i] - Close[i] : Close[i] - Open[i];
                if (body <= 0)
                    return false;
                if (i == SeqLen - 1 && body < atrNow * MinBodyAtr)
                    return false;
                if (body > prev)
                    return false;
                prev = body;
            }
            return true;
        }

        private void FlattenAll(string signal)
        {
            if (Position.MarketPosition == MarketPosition.Long)
                ExitLong(signal);
            else if (Position.MarketPosition == MarketPosition.Short)
                ExitShort(signal);
        }

        private static TimeZoneInfo FindNewYorkZone()
        {
            try { return TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time"); }
            catch { return TimeZoneInfo.FindSystemTimeZoneById("America/New_York"); }
        }

        #region Properties
        [NinjaScriptProperty, Range(2, 6)]
        [Display(Name = "Sequence length", GroupName = "1. Pattern", Order = 1)]
        public int SeqLen { get; set; }

        [NinjaScriptProperty, Range(0.0, 5.0)]
        [Display(Name = "Min first body (x ATR)", GroupName = "1. Pattern", Order = 2)]
        public double MinBodyAtr { get; set; }

        [NinjaScriptProperty, Range(1, 200)]
        [Display(Name = "ATR length", GroupName = "2. Exits", Order = 1)]
        public int AtrLen { get; set; }

        [NinjaScriptProperty, Range(0.1, 20.0)]
        [Display(Name = "Stop (x ATR)", GroupName = "2. Exits", Order = 2)]
        public double AtrSL { get; set; }

        [NinjaScriptProperty, Range(0.1, 20.0)]
        [Display(Name = "Target (x ATR)", GroupName = "2. Exits", Order = 3)]
        public double AtrTP { get; set; }

        [NinjaScriptProperty, Range(1000, 10000000)]
        [Display(Name = "Account size ($)", GroupName = "3. Risk", Order = 1)]
        public double AccountSize { get; set; }

        [NinjaScriptProperty, Range(0.1, 5.0)]
        [Display(Name = "Risk per trade (%)", GroupName = "3. Risk", Order = 2)]
        public double RiskPercent { get; set; }

        [NinjaScriptProperty, Range(1, 50)]
        [Display(Name = "Max contracts", GroupName = "3. Risk", Order = 3)]
        public int MaxContracts { get; set; }

        [NinjaScriptProperty, Range(50, 100000)]
        [Display(Name = "Max daily loss ($)", GroupName = "3. Risk", Order = 4)]
        public double MaxDailyLoss { get; set; }

        [NinjaScriptProperty, Range(0, 2359)]
        [Display(Name = "Entries from (NY HHmm)", GroupName = "4. Session", Order = 1)]
        public int SessionStartHHmm { get; set; }

        [NinjaScriptProperty, Range(0, 2359)]
        [Display(Name = "Entries until (NY HHmm)", GroupName = "4. Session", Order = 2)]
        public int SessionEndHHmm { get; set; }

        [NinjaScriptProperty, Range(0, 2359)]
        [Display(Name = "Flatten at (NY HHmm)", GroupName = "4. Session", Order = 3)]
        public int FlattenHHmm { get; set; }
        #endregion
    }
}
