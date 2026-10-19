"""Frozen-design treasury hedge calculations, separate from source acquisition.

Historical outcomes are reset one-month experiments on hypothetical zero bonds,
not an executable total-return strategy. No outcomes are computed on import.
"""
from datetime import date
import math
import numpy as np
from scipy.optimize import minimize

from retirement_alm.engine import key_weights
from gsw import month_ends


KEYS = np.array([1., 5., 10., 20., 30.])
TIMES = np.arange(1.,31.)
PAYMENTS = np.full(30,100.)
METHODS = ('five_year', 'duration_match', 'key_rate', 'covariance')


def liability_risk(curve, times=TIMES, payments=PAYMENTS):
    times, payments = np.asarray(times,dtype=float), np.asarray(payments,dtype=float)
    if (times.ndim != 1 or times.shape != payments.shape or not len(times) or
            np.any(~np.isfinite(times)) or np.any(~np.isfinite(payments)) or
            np.any(times <= 0) or np.any(payments < 0)):
        raise ValueError('Positive maturities and nonnegative matched cash flows required')
    present = payments*np.array([curve.discount(t) for t in times])
    pv = float(present.sum())
    if not math.isfinite(pv) or pv <= 0:
        raise ValueError('Positive finite liability value required')
    duration = float(present@times/pv)
    key_duration = (present*times)@key_weights(times)/pv
    return {'pv':pv, 'duration':duration, 'key_duration':key_duration}


def train_covariance(monthly):
    """Only 180 end-labelled train changes, January2000–December2014."""
    labels = sorted(monthly)
    changes = []
    endings = []
    for before, after in zip(labels,labels[1:]):
        if '2000-01' <= after <= '2014-12':
            changes.append([monthly[after].zero(t)-monthly[before].zero(t) for t in KEYS])
            endings.append(after)
    if len(changes) != 180 or endings[0] != '2000-01' or endings[-1] != '2014-12':
        raise ValueError('Incomplete or contaminated fixed training window')
    sample = np.cov(np.array(changes),rowvar=False,ddof=1)
    covariance = 0.75*sample+0.25*np.diag(np.diag(sample))
    validate_covariance(covariance)
    return covariance


def validate_covariance(covariance):
    covariance = np.asarray(covariance,dtype=float)
    if (covariance.shape != (5,5) or np.any(~np.isfinite(covariance)) or
            not np.allclose(covariance,covariance.T,rtol=0,atol=1e-14) or
            np.linalg.eigvalsh(covariance).min() < -1e-14):
        raise ValueError('Finite symmetric positive-semidefinite covariance required')
    return covariance


def hedge_weights(risk, covariance):
    covariance = validate_covariance(covariance)
    duration = risk['duration']
    target = np.asarray(risk['key_duration'],dtype=float)
    if target.shape != (5,) or np.any(~np.isfinite(target)) or not 5 <= duration <= 20:
        raise ValueError('Invalid risk vector or infeasible5/20-year duration match')
    weights = {'five_year':np.array([0.,1.,0.,0.,0.])}
    duration_weight = (20-duration)/15
    weights['duration_match'] = np.array([0.,duration_weight,0.,1-duration_weight,0.])
    for method in ('key_rate','covariance'):
        matrix = np.eye(5) if method == 'key_rate' else covariance
        ridge = 0 if method == 'key_rate' else 1e-8
        def objective(w):
            error = KEYS*w-target
            return float(error@matrix@error+ridge*(w@w))
        def gradient(w):
            error = KEYS*w-target
            return 2*KEYS*(matrix@error)+2*ridge*w
        solution = minimize(objective,np.full(5,0.2),jac=gradient,method='SLSQP',
            bounds=[(0,0.6)]*5,
            constraints=[{'type':'eq','fun':lambda w:w.sum()-1,'jac':lambda w:np.ones(5)}],
            options={'ftol':1e-12,'maxiter':1000})
        if (not solution.success or abs(solution.x.sum()-1)>1e-8 or
                np.any(solution.x < -1e-8) or np.any(solution.x > 0.6+1e-8)):
            raise ValueError('Hedge optimization failed: '+method)
        weights[method] = solution.x
    return weights


def holding_period_surplus(start, end, weights):
    elapsed = (end.asof-start.asof).days/365.25
    if not 0 < elapsed < 1:
        raise ValueError('Expected a positive holding interval shorter than first payment')
    weights = np.asarray(weights,dtype=float)
    if weights.shape != (5,) or np.any(~np.isfinite(weights)) or np.any(weights < -1e-8) or abs(weights.sum()-1)>1e-8:
        raise ValueError('Invalid fully funded asset weights')
    risk = liability_risk(start)
    faces = risk['pv']*weights/np.array([start.discount(t) for t in KEYS])
    assets = float(faces@np.array([end.discount(t-elapsed) for t in KEYS]))
    liabilities = float(PAYMENTS@np.array([end.discount(t-elapsed) for t in TIMES]))
    return (assets-liabilities)/risk['pv']


def experiments(monthly, covariance, *, first_end, last_end):
    labels = sorted(monthly)
    rows = []
    for before, after in zip(labels,labels[1:]):
        if not first_end <= after <= last_end:
            continue
        start, end = monthly[before], monthly[after]
        risk = liability_risk(start)
        for method, weights in hedge_weights(risk,covariance).items():
            rows.append({'start_date':str(start.asof),'end_date':str(end.asof),
                'end_month':after,'method':method,'weights':weights.tolist(),
                'initial_liability_pv':risk['pv'],
                'surplus_change_fraction':holding_period_surplus(start,end,weights)})
    return rows


def arrays_by_method(rows, expected_observations):
    if len(rows)!=len(METHODS)*expected_observations or any(row['method'] not in METHODS for row in rows):
        raise ValueError('Unexpected candidate or changed fixed prediction denominator')
    by_method = {}
    labels = None
    for method in METHODS:
        selected = [row for row in rows if row['method']==method]
        months = [row['end_month'] for row in selected]
        if len(selected)!=expected_observations or len(set(months))!=expected_observations:
            raise ValueError('Wrong fixed experiment denominator or duplicate observations')
        if labels is not None and months != labels:
            raise ValueError('Candidate calendars differ')
        labels = months
        values = np.array([row['surplus_change_fraction'] for row in selected])
        if np.any(~np.isfinite(values)):
            raise ValueError('Non-finite surplus result')
        by_method[method] = values
    return by_method


def summarize(values):
    values = np.asarray(values,dtype=float)
    if values.ndim != 1 or not len(values) or np.any(~np.isfinite(values)):
        raise ValueError('Finite experiment vector required')
    return {'observations':len(values),'rmse':float(np.sqrt(np.mean(values**2))),
            'bias':float(np.mean(values)),'mae':float(np.mean(np.abs(values))),
            'worst':float(np.min(values)),'empirical_fifth_percentile':float(np.quantile(values,0.05))}


def select_development(rows):
    arrays = arrays_by_method(rows,48)
    scores = {method:summarize(values) for method,values in arrays.items()}
    best = min(score['rmse'] for score in scores.values())
    selected = next(method for method in METHODS if scores[method]['rmse'] <= 1.01*best)
    return selected, scores


def paired_rmse_bootstrap(candidate, benchmark, *, draws=5000, block_length=6, seed=20261019):
    candidate, benchmark = np.asarray(candidate,dtype=float),np.asarray(benchmark,dtype=float)
    if (candidate.ndim!=1 or candidate.shape!=benchmark.shape or len(candidate)<block_length or
            type(draws) is not int or draws<=0 or type(block_length) is not int or block_length<=0 or
            np.any(~np.isfinite(candidate)) or np.any(~np.isfinite(benchmark))):
        raise ValueError('Valid paired vectors and bootstrap settings required')
    n = len(candidate); rng = np.random.default_rng(seed)
    starts = rng.integers(0,n,size=(draws,math.ceil(n/block_length)))
    indices = ((starts[:,:,None]+np.arange(block_length))%n).reshape(draws,-1)[:,:n]
    difference = np.sqrt(np.mean(candidate[indices]**2,axis=1))-np.sqrt(np.mean(benchmark[indices]**2,axis=1))
    return {'candidate_minus_benchmark_rmse':float(np.sqrt(np.mean(candidate**2))-np.sqrt(np.mean(benchmark**2))),
            'ci95':np.quantile(difference,[0.025,0.975]).tolist(),
            'draws':draws,'block_length_months':block_length,'seed':seed,'paired':True}
