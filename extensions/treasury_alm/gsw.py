"""Strict loaders for public GSW zero curves and SSA mortality statistics.

No network calls, fitting, imputation or performance claims are made here.
GSW yields and betas are percent; the public SVENY convention is continuous.
"""
from calendar import monthrange
from dataclasses import dataclass
from datetime import date
import csv
from io import StringIO
import math
import re


PARAMETERS = ('BETA0', 'BETA1', 'BETA2', 'BETA3', 'TAU1', 'TAU2')
ZEROS = tuple(f'SVENY{i:02d}' for i in range(1, 31))
MISSING = {'', 'NA', 'N/A', '.'}


def finite_number(value):
    if isinstance(value, bool):
        raise ValueError('Boolean is not a financial number')
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError('Invalid financial number') from error
    if not math.isfinite(number):
        raise ValueError('Non-finite financial number')
    return number


def svensson_zero(t, beta, tau1, tau2):
    """Continuously compounded decimal spot rate, including its t=0 limit."""
    t, tau1, tau2 = map(finite_number, (t, tau1, tau2))
    beta = tuple(map(finite_number, beta))
    if len(beta) != 4 or t < 0 or tau1 <= 0 or tau2 <= 0:
        raise ValueError('Invalid Svensson parameters or maturity')
    if t == 0:
        return finite_number((beta[0] + beta[1]) / 100)
    x1, x2 = t / tau1, t / tau2
    a1 = 1.0 if x1 == 0 else -math.expm1(-x1) / x1
    a2 = 1.0 if x2 == 0 else -math.expm1(-x2) / x2
    return finite_number((beta[0] + beta[1]*a1 + beta[2]*(a1-math.exp(-x1))
                          + beta[3]*(a2-math.exp(-x2))) / 100)


@dataclass(frozen=True)
class GSWCurve:
    asof: date
    beta: tuple
    tau1: float
    tau2: float
    quoted_zeros_percent: tuple

    def __post_init__(self):
        if not isinstance(self.asof, date) or len(self.quoted_zeros_percent) != 30:
            raise ValueError('Expected a date and all 30 published zero yields')
        svensson_zero(0, self.beta, self.tau1, self.tau2)
        for value in self.quoted_zeros_percent:
            finite_number(value)

    @classmethod
    def from_mapping(cls, row):
        return cls(date.fromisoformat(row['DATE']),
                   tuple(finite_number(row[k]) for k in PARAMETERS[:4]),
                   finite_number(row['TAU1']), finite_number(row['TAU2']),
                   tuple(finite_number(row[k]) for k in ZEROS))

    def zero(self, t):
        return svensson_zero(t, self.beta, self.tau1, self.tau2)

    def discount(self, t):
        t = finite_number(t)
        try:
            result = math.exp(-t*self.zero(t))
        except OverflowError as error:
            raise ValueError('Discount factor overflow') from error
        if not math.isfinite(result) or result <= 0:
            raise ValueError('Discount factor not finite and strictly positive')
        return result

    def reconcile(self, tolerance_bp=0.02):
        tolerance_bp = finite_number(tolerance_bp)
        if tolerance_bp <= 0:
            raise ValueError('Positive reconciliation tolerance required')
        errors = [abs(self.zero(i+1)-q/100)*10000
                  for i, q in enumerate(self.quoted_zeros_percent)]
        maximum = max(errors)
        if maximum > tolerance_bp:
            raise ValueError(f'Published zero-yield reconciliation failed: {maximum:.8g}bp')
        return maximum


def read_gsw_csv(text, lower='1999-12-01', upper='2026-09-30', *, quarantine_reconstruction=False):
    """Find the documented CSV header after metadata; return curves and audit.

    All-NA holiday rows and partially missing rows are recorded, never filled.
    Duplicate dates, malformed records, non-finite values and quote-convention
    mismatches fail rather than yielding a plausible-looking curve.
    """
    lower, upper = date.fromisoformat(lower), date.fromisoformat(upper)
    if type(quarantine_reconstruction) is not bool:
        raise ValueError('Explicit boolean reconstruction-quarantine policy required')
    if lower > upper:
        raise ValueError('Reversed input date window')
    lines = text.lstrip('\ufeff').splitlines()
    starts = [i for i, line in enumerate(lines)
              if re.match(r'^\s*Date\s*,', line, re.IGNORECASE)]
    if len(starts) != 1:
        raise ValueError('Expected exactly one GSW CSV header')
    reader = csv.DictReader(StringIO('\n'.join(lines[starts[0]:])))
    normalized = [name.strip().upper() for name in reader.fieldnames]
    if len(set(normalized)) != len(normalized):
        raise ValueError('Duplicate CSV columns')
    required = ('DATE',) + PARAMETERS + ZEROS
    if not set(required).issubset(normalized):
        raise ValueError('Missing GSW zero-yield or parameter columns')
    audit = {'valid_rows': 0, 'outside_window_rows': 0, 'all_missing_dates': [],
             'partial_missing_rows': [], 'quarantined_reconstruction_rows': [],
             'maximum_reconciliation_error_bp': 0.0}
    curves, seen = [], set()
    for raw in reader:
        if None in raw or any(value is None for value in raw.values()):
            raise ValueError('Ragged CSV row')
        row = {key.strip().upper(): value.strip() for key, value in raw.items()}
        observed = date.fromisoformat(row['DATE'])
        if observed in seen:
            raise ValueError('Duplicate curve date: ' + str(observed))
        seen.add(observed)
        if not lower <= observed <= upper:
            audit['outside_window_rows'] += 1
            continue
        missing = [key for key in required[1:] if row[key].upper() in MISSING]
        if len(missing) == len(required)-1:
            audit['all_missing_dates'].append(str(observed))
            continue
        if missing:
            audit['partial_missing_rows'].append({'date': str(observed), 'columns': missing})
            continue
        curve = GSWCurve.from_mapping(row)
        try:
            maximum = curve.reconcile()
        except ValueError:
            if not quarantine_reconstruction:
                raise
            errors = [abs(curve.zero(i+1)-q/100)*10000
                      for i,q in enumerate(curve.quoted_zeros_percent)]
            audit['quarantined_reconstruction_rows'].append({
                'date':str(observed),'maximum_error_bp':max(errors),
                'tolerance_bp':0.02,'reason':'Parameter reconstruction exceeds fixed tolerance'})
            continue
        audit['maximum_reconciliation_error_bp'] = max(audit['maximum_reconciliation_error_bp'], maximum)
        curves.append(curve)
    curves.sort(key=lambda curve: curve.asof)
    audit['valid_rows'] = len(curves)
    if not curves:
        raise ValueError('No complete curves inside the input window')
    return curves, audit


def month_ends(curves, start, end, max_stale_days=7):
    """Require a complete month grid. Never carry a prior month's curve."""
    if type(max_stale_days) is not int or max_stale_days < 0:
        raise ValueError('Invalid staleness allowance')
    first = date.fromisoformat(start + '-01')
    last = date.fromisoformat(end + '-01')
    if first > last:
        raise ValueError('Reversed monthly window')
    by_month = {}
    for curve in curves:
        label = curve.asof.strftime('%Y-%m')
        if label not in by_month or curve.asof > by_month[label].asof:
            by_month[label] = curve
    result, current = {}, first
    while current <= last:
        label = current.strftime('%Y-%m')
        cutoff = date(current.year, current.month, monthrange(current.year, current.month)[1])
        curve = by_month.get(label)
        if curve is None or (cutoff-curve.asof).days > max_stale_days:
            raise ValueError('Missing or stale complete monthly curve: ' + label)
        result[label] = curve
        current = date(current.year + (current.month == 12), current.month % 12 + 1, 1)
    return result


def read_ssa_qx(text):
    reader = csv.DictReader(StringIO(text))
    if reader.fieldnames != ['age', 'male_qx', 'female_qx']:
        raise ValueError('Unexpected mortality schema')
    table = {'male': {}, 'female': {}}
    for row in reader:
        age = int(row['age'])
        if not 0 <= age <= 119 or age in table['male']:
            raise ValueError('Duplicate or out-of-domain mortality age')
        for sex in table:
            qx = finite_number(row[sex + '_qx'])
            if not 0 <= qx <= 1:
                raise ValueError('Death probability outside [0,1]')
            table[sex][age] = qx
    if set(table['male']) != set(range(120)):
        raise ValueError('Incomplete official mortality age grid')
    return table
