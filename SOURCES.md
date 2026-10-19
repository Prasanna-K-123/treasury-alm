# Source and provenance ledger

The current release contains only the free public sources below and original
code/derived evidence. No source-owner outreach, account, API key, paid model
or paid dataset is required.

| Material | Official source | Pinned identity | Use and interpretation |
| --- | --- | --- | --- |
| GSW nominal curves | https://www.federalreserve.gov/data/nominal-yield-curve.htm | Original CSV16,657,704bytes; retrieved19October2026; last-modified13October2026 | SVENY continuously compounded percent. Downloaded historical values can be revised. |
| Original CSV | https://www.federalreserve.gov/data/yield-curve-tables/feds200628.csv | SHA256`7286435090933f0df1dcaeb15629f3a9129c083baee4c42ae5df03d0bb89335c` | Included unchanged as `feds200628.csv`; method rejects a different vintage. |
| GSW convention table | https://www.federalreserve.gov/data/yield-curve-tables/feds200628_1.html | SVENY, SVENPY, BETA and TAU conventions | SVENPY must not substitute for continuous zero yields. |
| GSW method paper | https://www.federalreserve.gov/pubs/feds/2006/200628/index.html | Gürkaynak, Sack and Wright nominal curve research | Curve fits are estimates, not directly executable zero-bond quotes. |
| SSA mortality | https://www.ssa.gov/oact/STATS/table4c6.html | 2023 period table used in2026Trustees Report;120ages, male/femaleqx | Derived transcription SHA256`1cc6300b231972794d25dbf8ed53f559ffe2557c2082e52d9e8774b66e41ae35`; population period table, not annuitant/cohort forecast. |

Federal Reserve source-use policy:
https://www.federalreserve.gov/disclaimer.htm.
SSA public-domain policy:
https://www.ssa.gov/policy/accessibility.html.
The MIT license for authored code does not relicense third-party material or
claim ownership of the government data. Agency marks, third-party artwork and
unrelated website content are not reproduced.

Source audit and documented quarantine are in
`extensions/treasury_alm/data/complete_source_audit.json` and
`reports/treasury_20261019/source_audit.json`. The original downloaded bytes
remain unchanged; exclusions apply only to explicitly invalid curve rows under
the frozen reconstruction rule. The two quarantined dates are not selected
month-ends. Every required month still passes the stale-data rule.

The SSA values were transcribed from the official normalized table; they are
not claimed to be an original downloaded HTML/CSV file. The raw Fed CSV is an
actual original byte download, with lossless transport hashes retained in its
source record. All contracts, scenario multipliers, haircuts and cash shifts
are synthetic assumptions; portfolio holdings are calculated, not observed.
