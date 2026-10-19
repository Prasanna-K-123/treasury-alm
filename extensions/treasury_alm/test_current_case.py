"""Independent analytic and cash-event boundaries for the current case."""
from dataclasses import dataclass
from datetime import date
import math
import unittest
import numpy as np

from current_case import (Cohort,ScenarioCurve,expected_payments,value,risk,
                          establish_portfolios,runoff)


@dataclass(frozen=True)
class FlatCurve:
    rate: float = .03
    asof: date = date(2026,9,30)
    def zero(self,t):return self.rate
    def discount(self,t):return math.exp(-self.rate*t)


def mortality(q=.1):
    return {sex:dict.fromkeys(range(120),q) for sex in ('male','female')}


class CurrentCaseTests(unittest.TestCase):
    def test_geometric_annuity_closed_form_and_duration(self):
        t,p,_ = expected_payments(mortality(),cohorts=(Cohort('male',60,3),),
                                  benefit=2,maximum_paying_age=65)
        curve=ScenarioCurve(FlatCurve())
        ratio=.9*math.exp(-.03);n=5
        closed=6*ratio*(1-ratio**n)/(1-ratio)
        duration=1/(1-ratio)-n*ratio**n/(1-ratio**n)
        self.assertAlmostEqual(value(t,p,curve),closed,places=12)
        self.assertAlmostEqual(risk(t,p,curve)['duration'],duration,places=12)

    def test_probability_endpoints_and_force_ordering(self):
        t,p,_=expected_payments(mortality(0),cohorts=(Cohort('male',118,2),),benefit=10)
        self.assertEqual(t.tolist(),[1.,2.]);self.assertEqual(p.tolist(),[20.,20.])
        _,p,_=expected_payments(mortality(1),cohorts=(Cohort('female',118),))
        self.assertEqual(p.tolist(),[0.,0.])
        curves=[expected_payments(mortality(),force=m)[1] for m in (.8,1.,1.2)]
        self.assertTrue(np.all(curves[0]>=curves[1]));self.assertTrue(np.all(curves[1]>=curves[2]))

    def test_terminal_payment_and_cohort_timing(self):
        full=expected_payments(mortality(0))[1]
        short=expected_payments(mortality(0),maximum_paying_age=110)[1]
        self.assertEqual(full[0],12000000.)
        self.assertEqual(full[44],12000000.)
        self.assertEqual(full[45],9000000.)
        self.assertEqual(full[-1],3000000.)
        self.assertEqual(len(full),60);self.assertEqual(len(short),50)
        self.assertEqual(short[-1],3000000.)

    def test_analytic_key_rates_and_parallel_derivatives(self):
        t,p,_=expected_payments(mortality(.02))
        result=risk(t,p,ScenarioCurve(FlatCurve()))
        self.assertAlmostEqual(sum(result['key_duration']),result['duration'],places=12)
        np.testing.assert_allclose(result['key_duration_fd'],result['key_duration'],rtol=1e-7,atol=1e-8)
        self.assertAlmostEqual(result['duration_fd']/result['duration'],1.,places=7)
        self.assertAlmostEqual(result['convexity_fd']/result['convexity'],1.,places=6)
        self.assertGreater(result['post30_pv_share'],0)

    def test_tail_continuity_and_flat_curve_equivalence(self):
        curves=[ScenarioCurve(FlatCurve(),tail=tail) for tail in ('svensson','flat_forward','flat_zero')]
        for t in (0.,1.,29.,30.,30.00001,60.):
            np.testing.assert_allclose([c.discount(t) for c in curves],math.exp(-.03*t),rtol=1e-14)
        shifted=ScenarioCurve(FlatCurve(),parallel=.005)
        self.assertAlmostEqual(shifted.discount(50)/curves[0].discount(50),math.exp(-.25),places=14)

    def test_initial_funding_and_duration_match(self):
        t,p,_=expected_payments(mortality(.1))
        curve=ScenarioCurve(FlatCurve());reference=risk(t,p,curve)
        portfolios=establish_portfolios(curve,t,p,np.eye(5)*1e-6)
        for item in portfolios.values():
            self.assertAlmostEqual(item['initial_assets_usd']/reference['pv'],1.,places=12)
            self.assertAlmostEqual(sum(item['weights']),1.,places=12)
        self.assertAlmostEqual(portfolios['duration_match']['asset_duration'],reference['duration'],places=12)
        for name in ('key_rate','covariance'):
            self.assertTrue(all(-1e-10<=w<=.6+1e-10 for w in portfolios[name]['weights']))

    def test_maturity_precedes_payment_and_no_unnecessary_sale(self):
        result=runoff([1.,2.],[80.,20.],ScenarioCurve(FlatCurve(0)),[100.,0.,0.,0.,0.],horizon=2,haircut=.5)
        self.assertEqual(result['gross_bond_sales_usd'],0.)
        self.assertEqual(result['years'][0]['closing_cash_usd'],20.)
        self.assertEqual(result['years'][0]['maturities_usd'],100.)
        self.assertEqual(result['final']['assets_usd'],0.)
        self.assertEqual(result['unpaid_nominal_usd'],0.)

    def test_liquidation_haircut_exhaustion_and_unpaid_obligation(self):
        result=runoff([1.,2.],[80.,80.],ScenarioCurve(FlatCurve(0)),[0.,100.,0.,0.,0.],horizon=2,haircut=.2)
        self.assertAlmostEqual(result['gross_bond_sales_usd'],100.)
        self.assertAlmostEqual(result['haircut_cost_usd'],20.)
        self.assertAlmostEqual(result['unpaid_nominal_usd'],80.)
        self.assertAlmostEqual(result['final']['surplus_usd'],0.)
        self.assertAlmostEqual(result['final']['surplus_after_unpaid_usd'],-80.)
        self.assertLess(result['discounted_wealth_max_abs_error_usd'],1e-12)

    def test_pro_rata_sales(self):
        result=runoff([1.],[20.],ScenarioCurve(FlatCurve(0)),[0.,50.,50.,0.,0.],horizon=1,haircut=.1)
        row=result['final'];gross=20/.9
        self.assertAlmostEqual(row['gross_bond_sales_usd'],gross)
        self.assertAlmostEqual(row['remaining_faces_usd'][1],50-gross/2)
        self.assertAlmostEqual(row['remaining_faces_usd'][2],50-gross/2)
        self.assertAlmostEqual(row['benefits_paid_usd'],20.)
        self.assertAlmostEqual(row['closing_cash_usd'],0.)

    def test_cash_reinvestment_and_forward_wealth_conservation(self):
        curve=ScenarioCurve(FlatCurve(.03))
        for shift in (-.01,0.,.01):
            result=runoff([1.,2.,3.],[5.,5.,5.],curve,[100.,0.,0.,0.,0.],horizon=3,cash_rate_shift=shift)
            cash=95.*math.exp(.03+shift)-5.
            cash=cash*math.exp(.03+shift)-5.
            self.assertAlmostEqual(result['final']['assets_usd'],cash,places=11)
            self.assertLess(result['discounted_wealth_max_abs_error_usd'],1e-11)

    def test_invalid_inputs_fail(self):
        for kwargs in ({'force':0},{'force':float('nan')},{'benefit':-1},{'maximum_paying_age':121},
                       {'maximum_paying_age':True},{'cohorts':()},{'cohorts':(Cohort('male',119),),'maximum_paying_age':110}):
            with self.assertRaises(ValueError):expected_payments(mortality(),**kwargs)
        for kwargs in ({'horizon':True},{'haircut':1},{'haircut':-.1},{'cash_rate_shift':float('inf')}):
            with self.assertRaises(ValueError):runoff([1.],[1.],ScenarioCurve(FlatCurve()),[1.,0.,0.,0.,0.],**kwargs)
        for bad in (-.01,1.01,float('nan'),True):
            table=mortality();table['male'][60]=bad
            with self.assertRaises(ValueError):expected_payments(table)
        for times,payments in (([1.,1.],[1.,2.]),([0.],[1.]),([1.],[-1.])):
            with self.assertRaises(ValueError):value(times,payments,ScenarioCurve(FlatCurve()))

    def test_sex_specific_survival_is_not_pooled(self):
        table={'male':dict.fromkeys(range(120),.1),'female':dict.fromkeys(range(120),.2)}
        t,p,details=expected_payments(table,cohorts=(Cohort('male',118,2),Cohort('female',118,3)),benefit=10)
        self.assertEqual(t.tolist(),[1.,2.])
        np.testing.assert_allclose(p,[2*10*.9+3*10*.8,2*10*.9**2+3*10*.8**2],atol=1e-12)
        self.assertEqual([d['sex'] for d in details],['male','female'])


if __name__=='__main__':unittest.main()
