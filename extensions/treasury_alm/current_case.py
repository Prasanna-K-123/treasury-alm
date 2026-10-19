"""Deterministic current ALM case; independent of sealed historical outcomes.

USD expected anniversary benefits, hypothetical zero holdings and declared
scenario assumptions. No network, fitting, source acquisition or paid services.
"""
from dataclasses import dataclass
import math
import numpy as np

from retirement_alm.engine import key_weights
from gsw import finite_number
from hedging import KEYS, hedge_weights, liability_risk


@dataclass(frozen=True)
class Cohort:
    sex: str
    age: int
    lives: float = 250.

    def __post_init__(self):
        if (self.sex not in ('male', 'female') or type(self.age) is not int or
                not 0 <= self.age < 120 or finite_number(self.lives) < 0):
            raise ValueError('Invalid cohort sex, exact age or lives')
        object.__setattr__(self,'lives',finite_number(self.lives))


COHORTS = (Cohort('male',60), Cohort('female',65),
           Cohort('male',70), Cohort('female',75))
BENEFIT = 12000.


def expected_payments(mortality, *, cohorts=COHORTS, benefit=BENEFIT,
                      force=1., maximum_paying_age=120):
    benefit, force = finite_number(benefit), finite_number(force)
    if (benefit < 0 or force <= 0 or type(maximum_paying_age) is not int or
            not 1 <= maximum_paying_age <= 120 or not cohorts):
        raise ValueError('Invalid benefit, mortality force or terminal age')
    if any(not isinstance(c,Cohort) or c.age >= maximum_paying_age for c in cohorts):
        raise ValueError('Every cohort must start before the maximum paying age')
    times = np.arange(1,maximum_paying_age-min(c.age for c in cohorts)+1,dtype=float)
    amounts = np.zeros(len(times))
    details = []
    for cohort in cohorts:
        survival = 1.
        payments, survivals = [], []
        for age in range(cohort.age,maximum_paying_age):
            try:
                q = finite_number(mortality[cohort.sex][age])
            except (KeyError,TypeError) as error:
                raise ValueError('Missing mortality source age or sex') from error
            if not 0 <= q <= 1:
                raise ValueError('Death probability outside [0,1]')
            survival *= math.exp(force*math.log1p(-q)) if q < 1 else 0.
            survivals.append(survival)
            payments.append(benefit*cohort.lives*survival)
        amounts[:len(payments)] += payments
        details.append({'sex':cohort.sex,'initial_age':cohort.age,
            'initial_lives':cohort.lives,'survival':survivals,'payments':payments})
    return times, amounts, details


@dataclass(frozen=True)
class ScenarioCurve:
    base: object
    parallel: float = 0.
    key_shifts: tuple = (0.,0.,0.,0.,0.)
    tail: str = 'svensson'

    def __post_init__(self):
        object.__setattr__(self,'parallel',finite_number(self.parallel))
        if self.tail not in ('svensson','flat_forward','flat_zero') or len(self.key_shifts)!=5:
            raise ValueError('Unknown tail or incorrect key-rate vector')
        object.__setattr__(self,'key_shifts',tuple(finite_number(v) for v in self.key_shifts))

    def discount(self,t):
        t = finite_number(t)
        if t < 0:
            raise ValueError('Negative maturity')
        if t <= 30 or self.tail == 'svensson':
            log_discount = -t*self.base.zero(t)
        elif self.tail == 'flat_zero':
            log_discount = -t*self.base.zero(30.)
        else:
            forward = 30*self.base.zero(30.)-29*self.base.zero(29.)
            log_discount = -30*self.base.zero(30.)-(t-30)*forward
        shock = self.parallel+float(key_weights([t])[0]@np.array(self.key_shifts))
        try:
            value = math.exp(log_discount-t*shock)
        except OverflowError as error:
            raise ValueError('Scenario discount factor overflow') from error
        if not math.isfinite(value) or value <= 0:
            raise ValueError('Scenario discount factor outside numeric domain')
        return value


def _cashflows(times,payments):
    t,p = np.asarray(times,dtype=float),np.asarray(payments,dtype=float)
    if (t.ndim!=1 or not len(t) or t.shape!=p.shape or
            not np.isfinite(t).all() or not np.isfinite(p).all() or
            np.any(t<=0) or np.any(np.diff(t)<=0) or np.any(p<0)):
        raise ValueError('Ordered positive maturities and nonnegative payments required')
    return t,p


def value(times,payments,curve):
    t,p = _cashflows(times,payments)
    result = float(p@np.array([curve.discount(x) for x in t]))
    if not math.isfinite(result):
        raise ValueError('Non-finite value')
    return result


def risk(times,payments,curve,bump=1e-5):
    t,p = _cashflows(times,payments)
    bump = finite_number(bump)
    if bump <= 0 or not isinstance(curve,ScenarioCurve):
        raise ValueError('Positive bump and scenario curve required')
    discounted = p*np.array([curve.discount(x) for x in t])
    pv = float(discounted.sum())
    if pv <= 0:
        raise ValueError('Positive liability PV required')
    duration = float(discounted@t/pv)
    convexity = float(discounted@(t*t)/pv)
    keys = (discounted*t)@key_weights(t)/pv
    def changed(parallel=0.,key=None):
        shifts = tuple(np.array(curve.key_shifts)+(np.zeros(5) if key is None else key))
        return ScenarioCurve(curve.base,curve.parallel+parallel,shifts,curve.tail)
    up,down = value(t,p,changed(bump)),value(t,p,changed(-bump))
    fd_keys = []
    for j in range(5):
        delta = np.zeros(5);delta[j]=bump
        fd_keys.append((value(t,p,changed(key=-delta))-value(t,p,changed(key=delta)))/(2*bump*pv))
    return {'pv':pv,'duration':duration,'convexity':convexity,
        'dv01_usd':duration*pv*.0001,'key_duration':keys.tolist(),
        'key_dv01_usd':(keys*pv*.0001).tolist(),
        'post30_pv_usd':float(discounted[t>30].sum()),
        'post30_pv_share':float(discounted[t>30].sum()/pv),
        'duration_fd':(down-up)/(2*bump*pv),
        'convexity_fd':(up+down-2*pv)/(bump*bump*pv),
        'key_duration_fd':fd_keys,'finite_difference_bump_decimal':bump}


def asset_value(faces,curve):
    faces = np.asarray(faces,dtype=float)
    if faces.shape!=(5,) or not np.isfinite(faces).all() or np.any(faces<0):
        raise ValueError('Five nonnegative finite zero-bond face amounts required')
    return float(faces@np.array([curve.discount(t) for t in KEYS]))


def establish_portfolios(curve,times,payments,covariance):
    base_risk = liability_risk(curve,times,payments)
    weights = hedge_weights(base_risk,covariance)
    result = {}
    for method,w in weights.items():
        faces = w*base_risk['pv']/np.array([curve.discount(t) for t in KEYS])
        result[method]={'weights':w.tolist(),'faces_usd':faces.tolist(),
            'initial_assets_usd':asset_value(faces,curve),
            'asset_duration':float(w@KEYS),
            'net_key_dv01_usd':((KEYS*w-base_risk['key_duration'])*base_risk['pv']*.0001).tolist()}
    return result


def runoff(times,payments,curve,faces,*,horizon=10,haircut=0.,cash_rate_shift=0.):
    """Expected runoff at initial-curve forwards; pro-rata sales before payments."""
    t,p = _cashflows(times,payments)
    haircut,cash_rate_shift = finite_number(haircut),finite_number(cash_rate_shift)
    if (type(horizon) is not int or horizon<1 or not 0<=haircut<1 or
            np.any(t!=np.floor(t))):
        raise ValueError('Integer annual cash-flow grid, horizon and valid haircut required')
    remaining = np.asarray(faces,dtype=float).copy()
    initial = asset_value(remaining,curve)
    cash,arrears,discounted_paid,discounted_loss,discounted_extra_interest = 0.,0.,0.,0.,0.
    rows = []
    for year in range(1,horizon+1):
        d0,d1 = curve.discount(year-1),curve.discount(year)
        forward_factor = d0/d1
        opening_cash = cash
        expected_interest = cash*(forward_factor-1)
        extra_interest = cash*forward_factor*math.expm1(cash_rate_shift)
        cash += expected_interest+extra_interest
        arrears *= forward_factor
        mature = KEYS==year
        maturities = float(remaining[mature].sum())
        cash += maturities;remaining[mature]=0.
        due = float(p[t==year].sum())
        marks = remaining*np.array([curve.discount(k)/d1 if k>year else 0. for k in KEYS])
        available = float(marks.sum())
        needed = max(due-cash,0.)
        fraction = min(needed/((1-haircut)*available),1.) if available>0 else 0.
        gross = available*fraction
        loss = gross*haircut
        remaining *= 1-fraction
        cash += gross-loss
        paid = min(due,cash)
        unpaid = max(due-paid,0.)
        arrears += unpaid
        cash = max(cash-paid,0.)
        bonds = float(remaining@np.array([curve.discount(k)/d1 if k>year else 0. for k in KEYS]))
        future = t>year
        liability = float(p[future]@np.array([curve.discount(k)/d1 for k in t[future]]))
        discounted_paid += paid*d1
        discounted_loss += loss*d1
        discounted_extra_interest += extra_interest*d1
        conservation = initial+discounted_extra_interest-discounted_paid-discounted_loss-(cash+bonds)*d1
        rows.append({'year':year,'opening_cash_usd':opening_cash,
            'base_cash_interest_usd':expected_interest,'extra_cash_interest_usd':extra_interest,
            'maturities_usd':maturities,'benefits_due_usd':due,'benefits_paid_usd':paid,
            'unpaid_benefits_usd':unpaid,'gross_bond_sales_usd':gross,'haircut_cost_usd':loss,
            'closing_cash_usd':cash,'remaining_faces_usd':remaining.tolist(),
            'assets_usd':cash+bonds,'remaining_liability_usd':liability,
            'surplus_usd':cash+bonds-liability,'unpaid_forward_carried_usd':arrears,
            'surplus_after_unpaid_usd':cash+bonds-liability-arrears,
            'discounted_wealth_conservation_error_usd':conservation})
    return {'horizon_years':horizon,'haircut':haircut,'cash_rate_shift_decimal':cash_rate_shift,
        'initial_assets_usd':initial,'gross_bond_sales_usd':sum(r['gross_bond_sales_usd'] for r in rows),
        'haircut_cost_usd':sum(r['haircut_cost_usd'] for r in rows),
        'unpaid_nominal_usd':sum(r['unpaid_benefits_usd'] for r in rows),
        'discounted_wealth_max_abs_error_usd':max(abs(r['discounted_wealth_conservation_error_usd']) for r in rows),
        'final':rows[-1],'years':rows}


def evaluate_current_case(base_curve,mortality,covariance):
    base = ScenarioCurve(base_curve)
    t,p,cohorts = expected_payments(mortality)
    base_risk = risk(t,p,base)
    portfolios = establish_portfolios(base,t,p,covariance)
    scenarios = [('base','base',0.,(0.,)*5,1.,120,'svensson')]
    for bp in (-200,-100,-50,50,100,200):
        scenarios.append((f'parallel_{bp:+d}bp','interest_rate',bp/10000,(0.,)*5,1.,120,'svensson'))
    for sign in (-1,1):
        scenarios.append((f'twist_short_{sign*50:+d}bp','interest_rate',0.,
            tuple(sign*x for x in (.005,.005,0.,-.005,-.005)),1.,120,'svensson'))
    for force in (.8,1.2):
        scenarios.append((f'mortality_force_{force}','longevity',0.,(0.,)*5,force,120,'svensson'))
    scenarios.append(('maximum_paying_age_110','terminal_age',0.,(0.,)*5,1.,110,'svensson'))
    for tail in ('flat_forward','flat_zero'):
        scenarios.append((tail+'_after30','curve_extrapolation',0.,(0.,)*5,1.,120,tail))
    instant = []
    for name,axis,shift,keys,force,terminal,tail in scenarios:
        curve = ScenarioCurve(base_curve,shift,keys,tail)
        times,payments,_ = expected_payments(mortality,force=force,maximum_paying_age=terminal)
        liability = value(times,payments,curve)
        for method,portfolio in portfolios.items():
            assets = asset_value(portfolio['faces_usd'],curve)
            instant.append({'scenario':name,'axis':axis,'method':method,'parallel_shift_decimal':shift,
                'key_shifts_decimal':list(keys),'mortality_force':force,'maximum_paying_age':terminal,
                'tail':tail,'assets_usd':assets,'liability_usd':liability,'surplus_usd':assets-liability,
                'surplus_fraction_initial_liability':(assets-liability)/base_risk['pv']})
    runoffs = []
    for force in (.8,1.,1.2):
        times,payments,_ = expected_payments(mortality,force=force)
        for haircut in (0.,.01,.02):
            for shift in (-.01,0.,.01):
                for method,portfolio in portfolios.items():
                    result = runoff(times,payments,base,portfolio['faces_usd'],
                        haircut=haircut,cash_rate_shift=shift)
                    runoffs.append({'method':method,'mortality_force':force,**result})
    return {'curve_date':str(base_curve.asof),'currency':'USD',
        'mortality_population':'SSA2023 period, Social Security area; not an annuitant/cohort forecast',
        'annual_benefit_per_life_usd':BENEFIT,'maximum_paying_age':120,
        'cohorts':cohorts,'times_years':t.tolist(),'expected_payments_usd':p.tolist(),
        'base_liability_risk':base_risk,'portfolios':portfolios,
        'instantaneous_scenarios':instant,'runoff_scenarios':runoffs,
        'scenario_counts':{'instantaneous_axis_cases':len(scenarios),
            'instantaneous_portfolio_results':len(instant),'runoff_cases':len(runoffs)},
        'historically_selected_method':'covariance',
        'historical_methods_refit_or_changed':False,
        'limits':['Expected synthetic benefits and hypothetical zero bonds, not a real plan or executable quotes.',
            'All stress asset faces are fixed at base inception; no stress-specific re-hedging.',
            'Period mortality is not cohort longevity. Beyond30year curve values are extrapolations.',
            'Static initial-curve forwards and haircut/cash-rate scenarios are assumptions, not forecasts.',
            'No calibrated probability, solvency capital, regulatory certification or realized profit.']}
