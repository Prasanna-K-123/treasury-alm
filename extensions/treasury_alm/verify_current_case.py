"""Separate Decimal arithmetic and event-ledger verification, not a model fit.

Prices, survival and runoff are independently reconstructed from raw inputs.
This verifier does not import the production curve, annuity or runoff functions.
"""
import argparse
import csv
from decimal import Decimal as D,localcontext
import hashlib
import io
from itertools import product
import json
from pathlib import Path
import numpy as np


KEYS=(1,5,10,20,30)
METHODS=('five_year','duration_match','key_rate','covariance')
COHORTS=(('male',60),('female',65),('male',70),('female',75))
USD_TOLERANCE=D('.0001')


def verify(source,evidence,historical,mortality_path):
    result=json.loads((evidence/'current_case.json').read_text())
    sha=lambda raw:hashlib.sha256(raw).hexdigest()
    assert sha(source.read_bytes())==result['provenance']['source_csv_sha256']
    assert sha(mortality_path.read_bytes())==result['provenance']['ssa_transcription_sha256']
    lines=source.read_text(encoding='utf-8-sig').splitlines()
    start=next(i for i,line in enumerate(lines) if line.lower().startswith('date,'))
    curve_rows=[row for row in csv.DictReader(io.StringIO('\n'.join(lines[start:]))) if row['Date']=='2026-09-30']
    assert len(curve_rows)==1 and result['curve_date']=='2026-09-30'
    raw=curve_rows[0];beta=[D(raw['BETA'+str(i)]) for i in range(4)]
    tau1,tau2=D(raw['TAU1']),D(raw['TAU2'])
    q={sex:{} for sex in ('male','female')}
    for row in csv.DictReader(io.StringIO(mortality_path.read_text())):
        age=int(row['age'])
        for sex in q:q[sex][age]=D(row[sex+'_qx'])
    assert all(set(table)==set(range(120)) for table in q.values())
    checks=0;max_usd=D(0);max_risk=D(0)
    def check(actual,expected,label,tolerance=USD_TOLERANCE):
        nonlocal checks,max_usd,max_risk
        error=abs(D(str(actual))-expected);checks+=1
        if tolerance==USD_TOLERANCE:max_usd=max(max_usd,error)
        else:max_risk=max(max_risk,error)
        if error>tolerance:raise AssertionError(f'{label}: absolute error {error} exceeds {tolerance}')
    def zero(t):
        t=D(t)
        if not t:return (beta[0]+beta[1])/100
        x1,x2=t/tau1,t/tau2
        a1=(1-(-x1).exp())/x1;a2=(1-(-x2).exp())/x2
        return (beta[0]+beta[1]*a1+beta[2]*(a1-(-x1).exp())+beta[3]*(a2-(-x2).exp()))/100
    def hats(t):
        t=D(t);w=[D(0)]*5
        if t<=1:w[0]=D(1)
        elif t>=30:w[4]=D(1)
        else:
            j=next(i for i in range(4) if KEYS[i]<=t<=KEYS[i+1])
            w[j]=(D(KEYS[j+1])-t)/D(KEYS[j+1]-KEYS[j]);w[j+1]=1-w[j]
        return w
    def discount(t,parallel=D(0),keys=(D(0),)*5,tail='svensson'):
        t=D(t)
        if t<=30 or tail=='svensson':logdf=-t*zero(t)
        elif tail=='flat_zero':logdf=-t*zero(30)
        else:logdf=-30*zero(30)-(t-30)*(30*zero(30)-29*zero(29))
        return (logdf-t*(parallel+sum(a*b for a,b in zip(hats(t),keys)))).exp()
    def payments(force=D(1),terminal=120):
        amounts=[D(0)]*60
        for sex,age in COHORTS:
            survival=D(1)
            for t in range(1,terminal-age+1):
                rate=q[sex][age+t-1]
                survival*=((1-rate).ln()*force).exp() if rate<1 else D(0)
                amounts[t-1]+=D(3000000)*survival
        return amounts
    df={t:discount(t) for t in range(61)}
    base_pay=payments();pv=sum(cf*df[t] for t,cf in enumerate(base_pay,1))
    current_risk=result['base_liability_risk']
    check(current_risk['pv'],pv,'base liability')
    duration=sum(D(t)*cf*df[t] for t,cf in enumerate(base_pay,1))/pv
    convexity=sum(D(t*t)*cf*df[t] for t,cf in enumerate(base_pay,1))/pv
    kd=[sum(D(t)*cf*df[t]*hats(t)[j] for t,cf in enumerate(base_pay,1))/pv for j in range(5)]
    for t,(actual,expected) in enumerate(zip(result['expected_payments_usd'],base_pay),1):check(actual,expected,f'payment {t}')
    check(current_risk['duration'],duration,'duration',D('1e-10'))
    check(current_risk['convexity'],convexity,'convexity',D('1e-9'))
    check(current_risk['dv01_usd'],duration*pv/D(10000),'DV01')
    check(current_risk['post30_pv_usd'],sum(base_pay[t-1]*df[t] for t in range(31,61)),'post30 PV')
    for j in range(5):
        check(current_risk['key_duration'][j],kd[j],f'key duration {j}',D('1e-10'))
        check(current_risk['key_duration_fd'][j],kd[j],f'finite-difference key {j}',D('.000002'))
    check(current_risk['duration_fd'],duration,'finite-difference duration',D('.000002'))
    check(current_risk['convexity_fd'],convexity,'finite-difference convexity',D('.0002'))
    assert result['currency']=='USD' and result['annual_benefit_per_life_usd']==12000
    portfolios=result['portfolios'];faces={}
    assert set(portfolios)==set(METHODS)
    for name,item in portfolios.items():
        w=[D(str(x)) for x in item['weights']]
        check(sum(w),D(1),name+' funding weights',D('1e-8'))
        assert min(w)>=D('-1e-8')
        if name in ('key_rate','covariance'):assert max(w)<=D('.60000001')
        faces[name]=[D(str(x)) for x in item['faces_usd']]
        for i,k in enumerate(KEYS):check(item['faces_usd'][i],pv*w[i]/df[k],name+' initial face')
        check(item['initial_assets_usd'],pv,name+' fully funded')
        check(item['asset_duration'],sum(D(k)*x for k,x in zip(KEYS,w)),name+' asset duration',D('1e-10'))
    check(portfolios['duration_match']['asset_duration'],duration,'duration-match identity',D('1e-10'))

    # Independent exhaustive active-face solutions of both convex QPs.
    target=np.array([float(x) for x in kd]);cov=np.array(result['provenance']['train_covariance']);nodes=np.diag(KEYS)
    qp={}
    for name,matrix,ridge in [('key_rate',np.eye(5),0.),('covariance',cov,1e-8)]:
        h=2*(nodes@matrix@nodes+ridge*np.eye(5));linear=-2*np.array(KEYS)*(matrix@target)
        best=float('inf')
        for pattern in product((-1,0,1),repeat=5):
            free=np.array([i for i,s in enumerate(pattern) if s==-1],dtype=int)
            fixed=np.array([i for i,s in enumerate(pattern) if s!=-1],dtype=int)
            if not len(free):continue
            w=np.array([.6 if s==1 else 0. for s in pattern])
            kkt=np.block([[h[np.ix_(free,free)],np.ones((len(free),1))],[np.ones((1,len(free))),np.zeros((1,1))]])
            rhs=np.r_[-linear[free]-h[np.ix_(free,fixed)]@w[fixed],1-w.sum()]
            w[free]=np.linalg.solve(kkt,rhs)[:-1]
            if min(w)<-1e-8 or max(w)>.6+1e-8:continue
            error=np.array(KEYS)*w-target
            best=min(best,float(error@matrix@error+ridge*w@w))
        actual=np.array(portfolios[name]['weights']);error=np.array(KEYS)*actual-target
        objective=float(error@matrix@error+ridge*actual@actual);gap=abs(objective-best)
        assert gap<=(1e-8 if name=='key_rate' else 2e-12),(name,gap)
        qp[name]={'enumerated_bound_faces':243,'objective_gap':gap}

    specs={'base':(D(0),(D(0),)*5,D(1),120,'svensson')}
    for bp in (-200,-100,-50,50,100,200):specs[f'parallel_{bp:+d}bp']=(D(bp)/10000,(D(0),)*5,D(1),120,'svensson')
    for sign in (-1,1):specs[f'twist_short_{sign*50:+d}bp']=(D(0),tuple(D(sign)*x for x in (D('.005'),D('.005'),D(0),D('-.005'),D('-.005'))),D(1),120,'svensson')
    for force in (D('.8'),D('1.2')):specs[f'mortality_force_{float(force)}']=(D(0),(D(0),)*5,force,120,'svensson')
    specs['maximum_paying_age_110']=(D(0),(D(0),)*5,D(1),110,'svensson')
    for tail in ('flat_forward','flat_zero'):specs[tail+'_after30']=(D(0),(D(0),)*5,D(1),120,tail)
    seen=set()
    for row in result['instantaneous_scenarios']:
        key=(row['scenario'],row['method']);assert key not in seen;seen.add(key)
        parallel,keys,force,terminal,tail=specs[row['scenario']]
        assert (D(str(row['parallel_shift_decimal'])),tuple(map(lambda x:D(str(x)),row['key_shifts_decimal'])),D(str(row['mortality_force'])),row['maximum_paying_age'],row['tail'])==(parallel,keys,force,terminal,tail)
        scenario_df={t:discount(t,parallel,keys,tail) for t in range(1,61)}
        liab=sum(cf*scenario_df[t] for t,cf in enumerate(payments(force,terminal),1))
        assets=sum(face*scenario_df[k] for face,k in zip(faces[row['method']],KEYS))
        check(row['assets_usd'],assets,'stressed assets');check(row['liability_usd'],liab,'stressed liability')
        check(row['surplus_usd'],assets-liab,'stressed surplus')
    assert seen==set(product(specs,METHODS)) and len(seen)==56

    years=list(csv.DictReader(io.StringIO((evidence/'runoff_years.csv').read_text())))
    assert len(years)==1080 and sha((evidence/'runoff_years.csv').read_bytes())==result['provenance']['runoff_year_csv_sha256']
    grid=set()
    for case in result['runoff_scenarios']:
        name=case['method'];force=D(str(case['mortality_force']));haircut=D(str(case['haircut']));shift=D(str(case['cash_rate_shift_decimal']))
        key=(name,force,haircut,shift);assert key not in grid;grid.add(key)
        records=[row for row in years if int(row['case_id'])==case['case_id']]
        assert [int(row['year']) for row in records]==list(range(1,11))
        holdings=faces[name].copy();cash=D(0);arrears=D(0);pays=payments(force)
        gross_sum=loss_sum=unpaid_sum=D(0)
        for year,row in enumerate(records,1):
            assert (row['method'],D(row['mortality_force']),D(row['haircut']),D(row['cash_rate_shift_decimal']))==key
            opening=cash;factor=df[year-1]/df[year]
            interest=cash*(factor-1);extra=cash*factor*(shift.exp()-1)
            cash+=interest+extra;arrears*=factor
            mature=sum(holdings[i] for i,k in enumerate(KEYS) if k==year)
            holdings=[D(0) if k==year else face for k,face in zip(KEYS,holdings)];cash+=mature
            available=sum(face*df[k]/df[year] for face,k in zip(holdings,KEYS) if k>year)
            due=pays[year-1];need=max(due-cash,D(0))
            sell=min(need/(1-haircut)/available,D(1)) if available else D(0)
            gross=available*sell;loss=gross*haircut
            holdings=[face*(1-sell) for face in holdings];cash+=gross-loss
            paid=min(cash,due);unpaid=due-paid;arrears+=unpaid;cash-=paid
            assets=cash+sum(face*df[k]/df[year] for face,k in zip(holdings,KEYS) if k>year)
            liability=sum(pays[t-1]*df[t]/df[year] for t in range(year+1,61))
            expected={'opening_cash_usd':opening,'base_cash_interest_usd':interest,'extra_cash_interest_usd':extra,
                'maturities_usd':mature,'benefits_due_usd':due,'benefits_paid_usd':paid,'unpaid_benefits_usd':unpaid,
                'gross_bond_sales_usd':gross,'haircut_cost_usd':loss,'closing_cash_usd':cash,'assets_usd':assets,
                'remaining_liability_usd':liability,'surplus_usd':assets-liability,'unpaid_forward_carried_usd':arrears,
                'surplus_after_unpaid_usd':assets-liability-arrears}
            expected.update({f'remaining_face_{k}y_usd':face for k,face in zip(KEYS,holdings)})
            for field,want in expected.items():check(row[field],want,f'runoff {case["case_id"]}/{year}/{field}')
            check(row['discounted_wealth_conservation_error_usd'],D(0),'wealth conservation')
            gross_sum+=gross;loss_sum+=loss;unpaid_sum+=unpaid
            if year==10:
                for field in ('assets_usd','remaining_liability_usd','surplus_usd','surplus_after_unpaid_usd'):
                    check(case['final'][field],expected[field],'final runoff '+field)
        for field,want in [('gross_bond_sales_usd',gross_sum),('haircut_cost_usd',loss_sum),('unpaid_nominal_usd',unpaid_sum)]:
            check(case[field],want,'runoff total '+field)
    assert grid==set(product(METHODS,(D('.8'),D(1),D('1.2')),(D(0),D('.01'),D('.02')),(D('-.01'),D(0),D('.01'))))
    historical_record=json.loads((historical/'historical_reproduction.json').read_text())
    for item in historical_record['scientific_outputs']:
        assert sha((historical/item['file']).read_bytes())==item['sha256']
    out={'status':'passed','arithmetic':'Independent Decimal pricing/survival/runoff at50digits; NumPy linear algebra for exhaustive convex-QP faces',
        'usd_absolute_tolerance':str(USD_TOLERANCE),'largest_usd_absolute_error':str(max_usd),
        'numeric_comparisons':checks,'instantaneous_results_checked':56,'runoff_year_records_checked':1080,
        'qp_independent_verification':qp,'historical_scientific_output_hashes_unchanged':5,
        'independent_workbook_finished':False,'whole_project_gate_B_accepted':False}
    with (evidence/'current_case_verification.json').open('x') as file:json.dump(out,file,indent=2);file.write('\n')
    print(json.dumps(out))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','evidence','historical','mortality'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    with localcontext() as context:
        context.prec=50
        verify(args.source,args.evidence,args.historical,args.mortality)
