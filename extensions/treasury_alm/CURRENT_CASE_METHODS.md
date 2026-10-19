# Current balance-sheet case: calculation details

This document specifies the separate current-case calculations before their
first execution on the official inputs. It does not alter the sealed historical
experiment, its candidates, selection rule, source vintage or final results.

The 30 September 2026 GSW curve discounts nominal USD benefits. Four synthetic
cohorts each contain 250 lives: male60, female65, male70 and female75. Each
surviving life receives USD12,000 at each anniversary. Survival to the payment
at age x+1 uses published q_x. Mortality force multiplier m transforms q to
1-(1-q)^m. The maximum paying age is120 (110 in the closure sensitivity):
payment at that birthday is allowed, and all payments after it are zero. This
is a disclosed truncation, equivalent to setting q_120=1 for an arrears annuity.
The SSA period table describes a population, not selected insured lives or
future cohort improvements. There are no stochastic mortality draws.

The base curve follows Svensson beyond30years. Alternatives preserve the curve
through30 and then use either the 29–30year continuously compounded forward
rate or the30year zero rate. These tails are assumptions, not observed quotes.
Report PV beyond30years, the maximum paying age110 sensitivity and both tails.

Four asset portfolios are established once against the base liability PV using
the historical protocol's hypothetical zero bonds and unchanged candidate
definitions. The covariance is still estimated only from2000–2014. Freeze those
initial face amounts for every stress. Do not rebalance after seeing a stress.
The historical selection remains covariance. Current-case comparisons are
deterministic sensitivities and cannot establish new out-of-sample superiority.

Instantaneous stresses are separate axes: six parallel shifts(+/-50/100/200bp),
two twists(+50bp at1/5years,0at10,-50bp at20/30; and its opposite), mortality
force0.8/1.0/1.2, maximum paying age110/120, and the two alternative tails.
Apply the piecewise-linear key-rate hats to a continuously compounded rate
shift. Report assets, liability and surplus for all four fixed portfolios.

The10year expected runoff uses the initial curve's deterministic forwards.
Cash earns D(y-1)/D(y) over year y. A declared cash-reinvestment sensitivity
multiplies this factor by exp(+/-0.01); it affects cash only, not bond marks or
liability discounting. Zero bonds mature before the anniversary payment. If
cash is insufficient, sell every remaining zero in the same proportion at
forward-implied marks D(T)/D(y), applying a0/1/2% liquidation haircut. The
haircut is an assumed cash loss on sales, not an observed bid/ask estimate.

Run the full3mortality x3haircut x3cash-rate grid for each of4portfolios
(108scenarios). Preserve each year's maturities, cash interest, paid and unpaid
benefits, sales, haircut losses, closing cash, remaining faces and liability.
Unpaid benefits are reported separately and do not silently disappear from a
positive-solvency claim: also report surplus after cumulative unpaid benefits
carried to the horizon at the same base forward rates. No calibrated shortfall
probability, solvency capital, regulatory valuation or realized profit is claimed.

Validation includes an independent geometric-annuity closed form, explicit
small cash-flow/liquidation examples, analytic versus finite-difference risk,
cash-flow/discounted-wealth conservation and a clean-directory deterministic
reproduction. The independent workbook and complete study release remain
separate acceptance requirements. Passing this component alone earns no new
whole-project gate.
