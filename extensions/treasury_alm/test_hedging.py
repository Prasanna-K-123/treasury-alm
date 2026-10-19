"""Independent analytical/synthetic checks; not historical outcome evidence."""
from dataclasses import replace
from datetime import date
import math
import unittest
import numpy as np

from gsw import GSWCurve
from hedging import (KEYS, TIMES, PAYMENTS, METHODS, liability_risk,
                     hedge_weights, holding_period_surplus, train_covariance,
                     select_development, paired_rmse_bootstrap)


class HedgeTests(unittest.TestCase):
    def setUp(self):
        self.curve=GSWCurve(date(2020,1,31),(3.,0.,0.,0.),1.,2.,(3.,)*30)
        self.covariance=np.eye(5)*1e-5

    def test_liability_value_matches_geometric_annuity_and_parallel_derivative(self):
        risk=liability_risk(self.curve)
        z=math.exp(-0.03)
        expected=100*z*(1-z**30)/(1-z)
        self.assertAlmostEqual(risk['pv'],expected,places=9)
        self.assertAlmostEqual(float(np.sum(risk['key_duration'])),risk['duration'],places=12)
        h=1e-5
        plus=replace(self.curve,beta=(3+100*h,0,0,0))
        minus=replace(self.curve,beta=(3-100*h,0,0,0))
        fd=(liability_risk(minus)['pv']-liability_risk(plus)['pv'])/(2*h*risk['pv'])
        self.assertAlmostEqual(fd,risk['duration'],places=6)

    def test_each_asset_book_is_fully_funded_and_duration_match_is_exact(self):
        risk=liability_risk(self.curve)
        weights=hedge_weights(risk,self.covariance)
        for method,w in weights.items():
            self.assertAlmostEqual(float(w.sum()),1.,places=8)
            self.assertGreaterEqual(float(w.min()),-1e-8)
            faces=risk['pv']*w/np.array([self.curve.discount(t) for t in KEYS])
            self.assertAlmostEqual(float(faces@np.array([self.curve.discount(t) for t in KEYS])),risk['pv'],places=8)
            if method in ('key_rate','covariance'):self.assertLessEqual(float(w.max()),0.6+1e-8)
        self.assertAlmostEqual(float(KEYS@weights['duration_match']),risk['duration'],places=12)

    def test_optimizer_matches_independent_enumeration_of_all_bound_faces(self):
        from itertools import product
        risk=liability_risk(self.curve)
        target=risk['key_duration']
        root=np.array([[1,.2,0,0,0],[.1,1,.2,0,0],[0,.1,1,.2,0],[0,0,.1,1,.2],[.1,0,0,.1,1.]])
        covariance=root@root.T*1e-5
        actual=hedge_weights(risk,covariance)
        for method,matrix,ridge in [('key_rate',np.eye(5),0),('covariance',covariance,1e-8)]:
            hessian=2*(np.diag(KEYS)@matrix@np.diag(KEYS)+ridge*np.eye(5))
            linear=-2*KEYS*(matrix@target)
            best=float('inf')
            for face in product((-1,0,1),repeat=5):
                free=np.array([i for i,s in enumerate(face) if s==-1],dtype=int)
                fixed=np.array([i for i,s in enumerate(face) if s!=-1],dtype=int)
                w=np.array([.6 if s==1 else 0. for s in face])
                if not len(free):continue
                kkt=np.block([[hessian[np.ix_(free,free)],np.ones((len(free),1))],
                              [np.ones((1,len(free))),np.zeros((1,1))]])
                rhs=np.r_[-linear[free]-hessian[np.ix_(free,fixed)]@w[fixed],1-w.sum()]
                w[free]=np.linalg.solve(kkt,rhs)[:-1]
                if np.any(w< -1e-8) or np.any(w>.6+1e-8):continue
                error=KEYS*w-target
                best=min(best,float(error@matrix@error+ridge*(w@w)))
            error=KEYS*actual[method]-target
            objective=float(error@matrix@error+ridge*(actual[method]@actual[method]))
            self.assertLessEqual(abs(objective-best),1e-10)

    def test_unchanged_flat_curve_carry_preserves_zero_surplus_for_every_book(self):
        end=replace(self.curve,asof=date(2020,2,28))
        for weights in hedge_weights(liability_risk(self.curve),self.covariance).values():
            self.assertAlmostEqual(holding_period_surplus(self.curve,end,weights),0.,places=12)

    def test_bad_funding_dates_and_covariance_fail(self):
        bad=np.ones(5)
        with self.assertRaises(ValueError):holding_period_surplus(self.curve,self.curve,bad)
        for covariance in (np.eye(5)*-1,np.eye(4),np.full((5,5),float('nan'))):
            with self.assertRaises(ValueError):hedge_weights(liability_risk(self.curve),covariance)
        with self.assertRaises(ValueError):hedge_weights({'duration':21,'key_duration':np.ones(5)},self.covariance)

    def test_training_covariance_ignores_all_development_and_final_changes(self):
        from calendar import monthrange
        curves={}
        for year in range(1999,2026):
            for month in range(1,13):
                if year==1999 and month!=12:continue
                label=f'{year}-{month:02d}'
                beta=(3+0.1*math.sin((year-1999)*12+month),0,0,0)
                curves[label]=replace(self.curve,asof=date(year,month,monthrange(year,month)[1]),beta=beta)
        first=train_covariance(curves)
        altered={k:replace(v,beta=(50,0,0,0)) if k>='2015-01' else v for k,v in curves.items()}
        np.testing.assert_array_equal(first,train_covariance(altered))
        del altered['2005-01']
        with self.assertRaises(ValueError):train_covariance(altered)

    def test_fixed_development_simplicity_rule_and_paired_bootstrap(self):
        rows=[]
        for i in range(48):
            for method,value in zip(METHODS,[0.01005,0.01,0.00999,0.00998]):
                rows.append({'method':method,'end_month':str(i),'surplus_change_fraction':value})
        # All four are within1% of the best: retain predeclared simplest.
        self.assertEqual(select_development(rows)[0],'five_year')
        paired=paired_rmse_bootstrap(np.full(84,0.01),np.full(84,0.02))
        self.assertAlmostEqual(paired['candidate_minus_benchmark_rmse'],-0.01)
        np.testing.assert_allclose(paired['ci95'],[-0.01,-0.01],atol=1e-15)
        self.assertEqual(paired,paired_rmse_bootstrap(np.full(84,0.01),np.full(84,0.02)))
        with self.assertRaises(ValueError):paired_rmse_bootstrap([1,2],[1])


if __name__=='__main__':unittest.main()
