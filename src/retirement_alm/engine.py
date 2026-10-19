from dataclasses import dataclass
import math
import numpy as np
from scipy.optimize import minimize

KEYS = np.array([1., 5., 10., 20., 30.])


@dataclass(frozen=True)
class Curve:
    times: tuple
    log_discounts: tuple
    extrapolation: str = "flat_forward"

    def __post_init__(self):
        t, l = np.asarray(self.times), np.asarray(self.log_discounts)
        if (len(t) < 2 or len(t) != len(l) or t[0] != 0 or l[0] != 0
                or not np.isfinite(t).all() or not np.isfinite(l).all()
                or not np.all(np.diff(t) > 0)):
            raise ValueError("Curve needs finite ordered nodes starting with (0, logDF=0)")
        if self.extrapolation not in ("flat_forward", "flat_zero"):
            raise ValueError("Unknown extrapolation")

    @classmethod
    def from_quotes(cls, times, rates, convention="continuous", extrapolation="flat_forward"):
        t, r = np.asarray(times, float), np.asarray(rates, float)
        if t.ndim != 1 or r.shape != t.shape or np.any(t <= 0):
            raise ValueError("Positive one-dimensional maturities required")
        if convention == "annual":
            if np.any(r <= -1):
                raise ValueError("Annual effective rates must exceed -100%")
            r = np.log1p(r)
        elif convention != "continuous":
            raise ValueError("Unknown quote convention")
        return cls(tuple(np.r_[0., t]), tuple(np.r_[0., -t*r]), extrapolation)

    def logdf(self, times):
        t = np.asarray(times, float)
        if np.any(~np.isfinite(t)) or np.any(t < 0):
            raise ValueError("Finite nonnegative times required")
        x, y = np.array(self.times), np.array(self.log_discounts)
        out = np.interp(t, x, y)
        slope = ((y[-1]-y[-2])/(x[-1]-x[-2])
                 if self.extrapolation == "flat_forward" else y[-1]/x[-1])
        return np.where(t > x[-1], y[-1]+(t-x[-1])*slope, out)

    def df(self, times):
        out = np.exp(self.logdf(times))
        if np.any(~np.isfinite(out)) or np.any(out <= 0):
            raise ValueError("Discount factors outside numeric domain")
        return out


def key_weights(times, knots=KEYS):
    """Linear hats, constant outside end knots: each row sums to one."""
    t, k = np.asarray(times, float), np.asarray(knots, float)
    if len(k) < 2 or np.any(np.diff(k) <= 0) or not np.isfinite(t).all():
        raise ValueError("Invalid key-rate grid")
    return np.stack([np.interp(t, k, np.eye(len(k))[j]) for j in range(len(k))], axis=-1)


def annuity(age, mortality, benefit=120000., count=1., force_scale=1., terminal_age=116):
    """Annual arrears survival payments, exact birthday at time zero."""
    if (not isinstance(age, int) or age < 0 or age > terminal_age
            or not math.isfinite(benefit) or benefit < 0
            or not math.isfinite(count) or count < 0
            or not math.isfinite(force_scale) or force_scale <= 0):
        raise ValueError("Invalid contract or mortality stress")
    survival, rows = 1., []
    for current in range(age, terminal_age+1):
        if current == terminal_age:
            q = 1.
        else:
            if current not in mortality:
                raise ValueError(f"Missing qx at age {current}")
            q = float(mortality[current])
            if not math.isfinite(q) or not 0 <= q <= 1:
                raise ValueError("qx outside [0,1]")
            q = -math.expm1(force_scale * math.log1p(-q)) if q < 1 else 1.
        survival *= 1-q
        t = current-age+1
        rows.append((t, current+1, q, survival, benefit*count*survival))
    return np.array(rows, dtype=float)


def aggregate(cohorts, mortality, benefit=120000., force_scale=1.):
    rows = [annuity(int(c['age']), mortality, benefit, c['count'], force_scale) for c in cohorts]
    times = np.arange(1, max(len(r) for r in rows)+1, dtype=float)
    amounts = np.zeros(len(times))
    for r in rows:
        amounts[:len(r)] += r[:, 4]
    return times, amounts


def value(times, amounts, curve, shift=0., key_shifts=None):
    t, cf = np.asarray(times, float), np.asarray(amounts, float)
    if t.shape != cf.shape or np.any(~np.isfinite(cf)):
        raise ValueError("Cash flow dimensions or values invalid")
    delta = np.full(t.shape, float(shift))
    if key_shifts is not None:
        ks = np.asarray(key_shifts, float)
        if ks.shape != (len(KEYS),) or not np.isfinite(ks).all():
            raise ValueError("Invalid key shocks")
        delta += key_weights(t) @ ks
    return float(np.sum(cf * curve.df(t) * np.exp(-t*delta)))


def risk(times, amounts, curve, bump=.0001):
    if bump <= 0 or not math.isfinite(bump):
        raise ValueError("Positive finite bump required")
    t, cf = np.asarray(times, float), np.asarray(amounts, float)
    p = cf*curve.df(t)
    pv = float(p.sum())
    if pv <= 0:
        raise ValueError("Positive PV required for normalized risks")
    up, down = value(t, cf, curve, bump), value(t, cf, curve, -bump)
    analytic_dollar = float((t*p).sum())
    kr = (t[:, None]*p[:, None]*key_weights(t)).sum(axis=0)
    kr_fd = []
    for j in range(len(KEYS)):
        k = np.zeros(len(KEYS)); k[j] = bump
        kr_fd.append((value(t, cf, curve, key_shifts=-k)-value(t, cf, curve, key_shifts=k))*.0001/(2*bump))
    return {'pv': pv, 'duration': analytic_dollar/pv, 'convexity': float((t*t*p).sum()/pv),
            'dv01': analytic_dollar*.0001, 'duration_fd': (down-up)/(2*bump*pv),
            'convexity_fd': (up+down-2*pv)/(bump*bump*pv),
            'key_dv01': (kr*.0001).tolist(), 'key_dv01_fd': kr_fd,
            'post30_pv_share': float(p[t > 30].sum()/pv)}


def hedge_weights(liability_risk):
    """Five zero bonds, PV weights; predeclared long-only constrained KRD hedge."""
    d = liability_risk['duration']
    if not 5 <= d <= 20:
        raise ValueError("Frozen 5/20-year duration comparator cannot match this liability")
    base = np.array([0., 1., 0., 0., 0.])
    dur = np.array([0., (20-d)/15, 0., (d-5)/15, 0.])
    target = np.asarray(liability_risk['key_dv01'])/(liability_risk['pv']*.0001)
    objective = lambda w: float(np.sum((KEYS*w-target)**2))
    fit = minimize(objective, np.full(5,.2), method='SLSQP',
                   bounds=[(0.,.6)]*5, constraints=[{'type':'eq','fun':lambda w: w.sum()-1}],
                   options={'ftol':1e-12,'maxiter':1000})
    if not fit.success or abs(fit.x.sum()-1) > 1e-8 or np.any(fit.x < -1e-8) or np.any(fit.x > .6+1e-8):
        raise RuntimeError('Constrained solver failed: '+fit.message)
    return {'unhedged_5y':base, 'duration_5y_20y':dur, 'constrained_key_rate':fit.x}, {
        'success':bool(fit.success), 'iterations':int(fit.nit), 'objective_years_squared':objective(fit.x),
        'target_key_duration':target.tolist(), 'sum_weight':float(fit.x.sum()),
        'cap':.6, 'long_only':True, 'optimizer_message':fit.message}


def runoff(times, amounts, curve, weights, initial_pv, horizon=10,
           reinvestment_shift=0., haircut=0., extra_payment=0.):
    """Deterministic runoff: cash earns implied forward; bonds sold pro-rata if needed.

    Static initial forward term structure is an assumption, not a forecast.
    Positive extra_payment at t=1 is an additional imposed liquidity expense.
    """
    if not 0 <= haircut < 1 or horizon < 1 or extra_payment < 0:
        raise ValueError('Invalid runoff assumptions')
    faces = np.asarray(weights,float)*initial_pv/curve.df(KEYS)
    cash, sales, haircut_cost, unpaid = 0., 0., 0., 0.
    for year in range(1,horizon+1):
        cash *= float(curve.df(year-1)/curve.df(year))*math.exp(reinvestment_shift)
        mature = KEYS == year
        cash += float(faces[mature].sum()); faces[mature] = 0
        due = float(np.asarray(amounts)[np.asarray(times)==year].sum()) + (extra_payment if year == 1 else 0.)
        need = max(due-cash,0.)
        marks = faces * curve.df(KEYS)/curve.df(year)
        available = float(marks.sum())
        sell_fraction = min(need/((1-haircut)*available),1.) if available > 0 else 0.
        gross = sell_fraction*available
        faces *= 1-sell_fraction
        cash += gross*(1-haircut); sales += gross; haircut_cost += gross*haircut
        unpaid += max(due-cash,0.); cash = max(cash-due,0.)
    assets = cash + float(np.sum(faces*curve.df(KEYS)/curve.df(horizon)))
    future = np.asarray(times) > horizon
    remaining = value(np.asarray(times)[future],np.asarray(amounts)[future],curve)/float(curve.df(horizon))
    return {'horizon':horizon,'assets':assets,'remaining_liability':remaining,'surplus':assets-remaining,
            'gross_bond_sales':sales,'haircut_cost':haircut_cost,'unpaid_nominal':unpaid,
            'reinvestment_shift':reinvestment_shift,'haircut':haircut,'extra_liquidity_expense':extra_payment}
