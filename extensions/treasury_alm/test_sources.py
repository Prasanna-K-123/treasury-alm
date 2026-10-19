"""Source/valuation boundaries; only the stated official fixtures are real data."""
from dataclasses import replace
from datetime import date
import csv
from io import StringIO
import json
import math
from pathlib import Path
import unittest

from gsw import GSWCurve, PARAMETERS, ZEROS, month_ends, read_gsw_csv, read_ssa_qx, svensson_zero

HERE = Path(__file__).resolve().parent


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads((HERE/'data/gsw_official_fixture_20241129.json').read_text())
        params = self.fixture['parameters']
        self.curve = GSWCurve(date(2024,11,29), tuple(params[k] for k in PARAMETERS[:4]),
                              params['TAU1'], params['TAU2'],
                              tuple(self.fixture['zero_yields_percent'][str(i)] for i in range(1,31)))

    def csv(self, rows):
        output = StringIO()
        output.write('Source fixture, not the original downloaded CSV\n')
        writer = csv.writer(output)
        writer.writerow(['Date', *PARAMETERS, *ZEROS])
        writer.writerows(rows)
        return output.getvalue()

    def row(self, day='2024-11-29'):
        return [day, *self.curve.beta, self.curve.tau1, self.curve.tau2,
                *self.curve.quoted_zeros_percent]

    def test_actual_official_parameters_reconstruct_all_thirty_zero_yields(self):
        self.assertLessEqual(self.curve.reconcile(), 0.005001)

    def test_actual_official_ssa_table_complete_and_known_cells(self):
        table = read_ssa_qx((HERE/'data/ssa_2023_period_qx.csv').read_text())
        self.assertEqual(set(table['male']), set(range(120)))
        self.assertEqual(table['male'][65], 0.016455)
        self.assertEqual(table['female'][65], 0.010188)
        self.assertEqual(table['male'][119], 0.926604)

    def test_continuous_discount_convention_and_zero_maturity_limit(self):
        self.assertEqual(self.curve.discount(0), 1.0)
        self.assertAlmostEqual(self.curve.zero(0), sum(self.curve.beta[:2])/100)
        self.assertAlmostEqual(self.curve.discount(10), math.exp(-10*self.curve.zero(10)))
        self.assertGreater(abs(self.curve.discount(10)-(1+self.curve.zero(10))**-10), 0.001)

    def test_negative_yields_are_valid_and_bad_maturities_fail(self):
        negative = GSWCurve(date(2024,1,1), (-2,0,0,0), 1,2,(-2,)*30)
        self.assertAlmostEqual(negative.discount(5), math.exp(0.1))
        for t in (-1, float('nan'), float('inf')):
            with self.assertRaises(ValueError): self.curve.discount(t)
        for tau in (0,-1,float('nan')):
            with self.assertRaises(ValueError): svensson_zero(10,(1,2,3,4),tau,1)
        self.assertAlmostEqual(svensson_zero(1e-300,(1,2,3,4),1e300,1e300),0.03)
        with self.assertRaises(ValueError): svensson_zero(0,(1e308,1e308,0,0),1,2)

    def test_par_yield_substitution_is_detected(self):
        altered = replace(self.curve, quoted_zeros_percent=(5,)*30)
        with self.assertRaises(ValueError): altered.reconcile()

    def test_csv_roundtrip_records_missing_observations_and_never_imputes(self):
        missing = ['2024-11-28'] + ['NA']*36
        partial = self.row('2024-11-27'); partial[1] = 'NA'
        curves, audit = read_gsw_csv(self.csv([self.row(), missing, partial]))
        self.assertEqual([c.asof for c in curves], [date(2024,11,29)])
        self.assertEqual(audit['all_missing_dates'], ['2024-11-28'])
        self.assertEqual(audit['partial_missing_rows'], [{'date':'2024-11-27','columns':['BETA0']}])

    def test_csv_duplicate_ragged_and_convention_failures(self):
        wrong = self.row(); wrong[7] = 99
        for rows in ([self.row(),self.row()], [self.row()[:-1]], [wrong]):
            with self.assertRaises(ValueError): read_gsw_csv(self.csv(rows))

    def test_quarantine_is_explicit_and_keeps_fixed_quote_tolerance(self):
        bad = self.row('2024-11-27'); bad[7] = 99
        text = self.csv([bad,self.row()])
        with self.assertRaises(ValueError):read_gsw_csv(text)
        curves,audit=read_gsw_csv(text,quarantine_reconstruction=True)
        self.assertEqual(len(curves),1)
        self.assertEqual(audit['quarantined_reconstruction_rows'][0]['date'],'2024-11-27')
        self.assertEqual(audit['quarantined_reconstruction_rows'][0]['tolerance_bp'],0.02)
        with self.assertRaises(ValueError):read_gsw_csv(self.csv([bad]),quarantine_reconstruction=True)

    def test_quarantine_cannot_hide_a_missing_month_end(self):
        stale = self.row('2024-11-20'); bad = self.row();bad[7]=99
        curves,audit=read_gsw_csv(self.csv([stale,bad]),quarantine_reconstruction=True)
        with self.assertRaises(ValueError):month_ends(curves,'2024-11','2024-11')

    def test_month_end_selection_cannot_use_future_or_carry_missing_month(self):
        curves = [replace(self.curve, asof=date(2024,11,27)), self.curve,
                  replace(self.curve, asof=date(2024,12,2))]
        selected = month_ends(curves,'2024-11','2024-11')
        self.assertEqual(selected['2024-11'].asof, date(2024,11,29))
        with self.assertRaises(ValueError): month_ends(curves,'2024-11','2024-12')
        with self.assertRaises(ValueError): month_ends(curves,'2024-10','2024-11')

    def test_complete_calendar_has_313_curves_and_312_end_labelled_intervals(self):
        curves = []
        for year in range(1999,2026):
            for month in range(1,13):
                if year == 1999 and month != 12: continue
                # A synthetic calendar fixture, not historical rates.
                from calendar import monthrange
                curves.append(replace(self.curve, asof=date(year,month,monthrange(year,month)[1])))
        grid = month_ends(curves,'1999-12','2025-12')
        self.assertEqual(len(grid),313)
        endings = list(grid)[1:]
        self.assertEqual(sum(x <= '2014-12' for x in endings),180)
        self.assertEqual(sum('2015-01' <= x <= '2018-12' for x in endings),48)
        self.assertEqual(sum('2019-01' <= x <= '2025-12' for x in endings),84)

    def test_mortality_rejects_missing_duplicate_and_invalid_rows(self):
        original = (HERE/'data/ssa_2023_period_qx.csv').read_text()
        for bad in (original.rsplit('\n',2)[0]+'\n', original+'65,0.1,0.1\n',
                    original.replace('0.016455','1.016455')):
            with self.assertRaises(ValueError): read_ssa_qx(bad)


if __name__ == '__main__': unittest.main()
