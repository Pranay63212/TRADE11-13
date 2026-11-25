// AMD + Time + IFVG, 0.5R target - NinjaTrader 8 strategy (NinjaScript).
// Same rules as bot/strategy.py and tradingview/amd_ifvg_lucid_traderspost.pine:
//   Asian range : bars starting 20:00-23:55 New York time.
//   Bias        : first sweep of the Asian low (-> long) or high (-> short) from 00:00 to 11:00 NY.
//   Entry       : 5-min close through the latest opposing FVG formed since midnight, only in the
//                 killzones 02:00-05:00 and 08:30-11:00 NY. One trade per day.
//   Stop        : lowest low (long) / highest high (short) since midnight.  Target: 0.5R.
//   Exit        : flat by 15:55 NY.
// Use on an MNQ 5-minute chart. Not compiled inside NinjaTrader yet: if it shows an error,
// send the error text. Install: copy this file to
//   Documents\NinjaTrader 8\bin\Custom\Strategies\  then open the NinjaScript Editor and press F5.
#region Using declarations
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
#endregion

namespace NinjaTrader.NinjaScript.Strategies
{
    public class AmdIfvgHalfR : Strategy
    {
        private TimeZoneInfo ny;
        private double aHi, aLo;
        private int aBars;
        private int bias;
        private double runLo, runHi, bearTop, bullBot;
        private bool hasBearTop, hasBullBot;
        private int sessBars;
        private bool done;
        private int prevHour = -1;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "AmdIfvgHalfR";
                Description = "AMD + IFVG, 0.5R target, one trade per day (MNQ 5-minute).";
                Calculate = Calculate.OnBarClose;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 30;
                BarsRequiredToTrade = 3;
                StartBehavior = StartBehavior.WaitUntilFlat;
                RiskDollars = 200;
                MaxContracts = 20;
                CostPoints = 1.0;
                TargetR = 0.5;
                MinAsiaBars = 24;
            }
            else if (State == State.DataLoaded)
            {
                ny = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
                ResetDay();
                aBars = 0;
                if (BarsPeriod.BarsPeriodType != BarsPeriodType.Minute || BarsPeriod.Value != 5)
                    Print("AmdIfvgHalfR WARNING: use a 5-minute chart. Current: " + BarsPeriod.ToString());
            }
        }

        private void ResetDay()
        {
            bias = 0;
            runLo = double.MaxValue;
            runHi = double.MinValue;
            hasBearTop = false;
            hasBullBot = false;
            sessBars = 0;
            done = false;
        }

        protected override void OnBarUpdate()
        {
            if (BarsInProgress != 0 || CurrentBar < 3)
                return;

            // NinjaTrader time stamps a bar at its CLOSE; convert the bar START to New York time.
            DateTime barStart = Time[0].AddMinutes(-BarsPeriod.Value);
            DateTime t = TimeZoneInfo.ConvertTime(barStart, Core.Globals.GeneralOptions.TimeZoneInfo, ny);
            int h = t.Hour;
            int mins = h * 60 + t.Minute;

            // ---- Accumulation: Asian range 20:00-23:55 NY
            if (h >= 20)
            {
                if (prevHour < 20)
                {
                    aHi = High[0];
                    aLo = Low[0];
                    aBars = 1;
                }
                else
                {
                    aHi = Math.Max(aHi, High[0]);
                    aLo = Math.Min(aLo, Low[0]);
                    aBars++;
                }
            }
            // ---- New day starts with the first bar after the Asian window
            if (h < 20 && prevHour >= 20)
                ResetDay();
            prevHour = h;

            // ---- End-of-day exit (bar starting 15:50 closes at 15:55)
            if (Position.MarketPosition != MarketPosition.Flat && mins >= 15 * 60 + 50 && h < 17)
            {
                if (Position.MarketPosition == MarketPosition.Long) ExitLong();
                else ExitShort();
                return;
            }

            bool inKillzone = (mins >= 120 && mins < 300) || (mins >= 510 && mins < 660);
            bool goLong = false, goShort = false;

            if (h < 11 && !done && aBars >= MinAsiaBars)
            {
                sessBars++;
                runLo = Math.Min(runLo, Low[0]);
                runHi = Math.Max(runHi, High[0]);
                if (sessBars >= 3)
                {
                    if (High[0] < Low[2]) { bearTop = Low[2]; hasBearTop = true; }
                    if (Low[0] > High[2]) { bullBot = High[2]; hasBullBot = true; }
                }
                if (bias == 0)
                {
                    if (Low[0] < aLo) bias = 1;
                    else if (High[0] > aHi) bias = -1;
                    if (bias != 0)
                        Print(string.Format("{0} NY  bias {1} (Asian high {2}, low {3})", t, bias > 0 ? "LONG" : "SHORT", aHi, aLo));
                }
                else if (inKillzone)
                {
                    goLong = bias == 1 && hasBearTop && Close[0] > bearTop;
                    goShort = bias == -1 && hasBullBot && Close[0] < bullBot;
                }
            }

            if ((goLong || goShort) && Position.MarketPosition == MarketPosition.Flat)
            {
                done = true;
                double stop = goLong ? runLo : runHi;
                double dist = Math.Abs(Close[0] - stop);
                if (dist <= 0)
                    return;
                int qty = (int)Math.Min(MaxContracts,
                    Math.Floor(RiskDollars / ((dist + CostPoints) * Instrument.MasterInstrument.PointValue)));
                if (qty < 1)
                {
                    Print(string.Format("{0} NY  setup skipped: stop {1:0.00} pts is too wide for ${2} risk", t, dist, RiskDollars));
                    return;
                }
                double target = goLong ? Close[0] + TargetR * dist : Close[0] - TargetR * dist;
                stop = Instrument.MasterInstrument.RoundToTickSize(stop);
                target = Instrument.MasterInstrument.RoundToTickSize(target);
                string sig = goLong ? "L" : "S";
                SetStopLoss(sig, CalculationMode.Price, stop, false);
                SetProfitTarget(sig, CalculationMode.Price, target);
                if (goLong) EnterLong(qty, sig);
                else EnterShort(qty, sig);
                Print(string.Format("{0} NY  ENTER {1} {2} contracts, stop {3}, target {4}", t, sig, qty, stop, target));
            }
        }

        #region Properties
        [NinjaScriptProperty]
        [Range(1, double.MaxValue)]
        [Display(Name = "Risk $ per trade (eval 200, funded 150)", Order = 1, GroupName = "Parameters")]
        public double RiskDollars { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Max contracts (Lucid 25K: 20 micros)", Order = 2, GroupName = "Parameters")]
        public int MaxContracts { get; set; }

        [NinjaScriptProperty]
        [Range(0, double.MaxValue)]
        [Display(Name = "Cost per contract (points)", Order = 3, GroupName = "Parameters")]
        public double CostPoints { get; set; }

        [NinjaScriptProperty]
        [Range(0.1, double.MaxValue)]
        [Display(Name = "Target in R", Order = 4, GroupName = "Parameters")]
        public double TargetR { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Min 5-min bars in Asian range", Order = 5, GroupName = "Parameters")]
        public int MinAsiaBars { get; set; }
        #endregion
    }
}
