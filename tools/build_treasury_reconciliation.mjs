import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {Workbook, SpreadsheetFile, FileBlob} from '@oai/artifact-tool';

const inputPath=process.env.TREASURY_WORKBOOK_INPUT;
const output=process.env.TREASURY_WORKBOOK_OUTPUT;
if(!inputPath || !output)throw Error('Set TREASURY_WORKBOOK_INPUT and TREASURY_WORKBOOK_OUTPUT to absolute paths.');
const raw=await fs.readFile(inputPath);
const data=JSON.parse(raw.toString('utf8'));
if(data.schema!=='treasury-workbook-inputs-v1')throw Error('Unknown input schema.');
await fs.mkdir(output,{recursive:true});
const wb=Workbook.create();
const names=['ALM review','Controls','Benefits','Curve','Runoff','Historical','Sources'];
const sheets=Object.fromEntries(names.map(n=>[n,wb.worksheets.add(n)]));
const [review,controls,benefits,curve,runoff,historical,sources]=names.map(n=>sheets[n]);
const navy='#193B58',light='#EDF3F8',ink='#172B3A',muted='#526475',green='#008000',blue='#0000FF';
const money='[>=0.005]#,##0.00;[<=-0.005](#,##0.00);"-"';
const letter=n=>{let s='';for(n+=3;n>0;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s;};
const addr=(n,r)=>`${letter(n)}${r}`;
const absolute=(n,r)=>`$${letter(n)}$${r}`;
const xr=(s,n,r)=>`'${s}'!${absolute(n,r)}`;
const set=(s,c,value)=>s.getRange(c).values=[[value]];
const form=(s,c,value)=>s.getRange(c).formulas=[[value]];
const sel=r=>xr('Controls',3,r);
const source=(c,r)=>xr('Sources',c,r);
const title=(s,text,last='M',rows=150)=>{
 s.showGridLines=false;
 s.getRange(`A1:${last}${rows}`).format={font:{name:'Arial',size:10,color:ink},rowHeight:20,verticalAlignment:'center'};
 s.getRange(`A1:A${rows}`).format.columnWidth=3;
 s.getRange(`B1:B${rows}`).format.columnWidth=2;
 s.getRange(`C1:${last}${rows}`).format.columnWidth=16;
 set(s,'C2',text);s.getRange('C2').format.font={name:'Arial',size:14,bold:true,color:navy};
 s.getRange(`C2:${last}2`).format.borders={bottom:{style:'thin',color:'#A4B2BE'}};
};
const header=(s,range)=>s.getRange(range).format={fill:navy,font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:34,horizontalAlignment:'center',verticalAlignment:'center',borders:{insideVertical:{style:'thin',color:'#FFFFFF'}}};
const section=(s,row,text,last='M')=>{set(s,`C${row}`,text);s.getRange(`C${row}:${last}${row}`).format={fill:light,font:{name:'Arial',size:10,bold:true,color:navy},rowHeight:24};};
const note=(s,cell,text)=>{set(s,cell,text);s.getRange(cell).format.font={name:'Arial',size:10,italic:true,color:muted};};
const m=data.methods, labels=data.method_labels,keys=[1,5,10,20,30];
title(review,'Treasury ALM valuation and liquidity','K',42);review.tabColor=navy;
title(controls,'Scenario inputs','G',28);controls.tabColor='#5B7E99';
title(benefits,'Expected benefit cash flows','W',139);
title(curve,'Svensson curve and rate stresses','R',128);
title(runoff,'Ten-year expected runoff','M',60);
title(historical,'Historical hedge reconciliation','N',149);
title(sources,'Pinned source inputs','O',139);
for(const s of [benefits,curve,runoff,historical]){
 set(s,'C3','Portfolio');form(s,'D3',`=INDEX('Sources'!$H$7:$K$7,1,${sel(4)})`);
 s.getRange('D3').format.font.color=green;
}

// Source observations and the fixed inception holdings remain independent of scenarios.
set(sources,'C4','Current curve date');set(sources,'D4',new Date(data.current_curve.date+'T00:00:00Z'));
sources.getRange('D4').setNumberFormat('dd-mmm-yyyy');
sources.getRange('C6:D11').values=['BETA0 (%)','BETA1 (%)','BETA2 (%)','BETA3 (%)','TAU1 (years)','TAU2 (years)'].map((x,j)=>[x,j<4?data.current_curve.beta[j]:data.current_curve[j===4?'tau1':'tau2']]);
sources.getRange('D6:D11').setNumberFormat('0.00000000');
sources.getRange('C14:E14').values=[['Age last birthday','Male qx','Female qx']];header(sources,'C14:E14');
sources.getRange('C15:E134').values=data.mortality.map(r=>[r.age,r.male_qx,r.female_qx]);
sources.getRange('D15:E134').setNumberFormat('0.000000');
set(sources,'G5','Fixed inception zero-bond faces (USD)');
sources.getRange('G7:K7').values=[['Maturity (years)',...labels]];header(sources,'G7:K7');
sources.getRange('G8:K12').values=keys.map((t,j)=>[t,...m.map(method=>data.current_reference.portfolios[method].faces_usd[j])]);
sources.getRange('H8:K12').setNumberFormat(money);
sources.getRange('G15:I15').values=[['Maturity (years)','Published SVENY','Reconstruction error (bp)']];header(sources,'G15:I15');
sources.getRange('G16:H45').values=data.current_curve.quoted_zeros_percent.map((y,j)=>[j+1,y/100]);
sources.getRange('H16:H45').setNumberFormat('0.000000%');
sources.getRange('G48:J48').values=[['Cohort','Sex','Initial age','Initial lives']];header(sources,'G48:J48');
sources.getRange('G49:J52').values=data.current_reference.cohorts.map(c=>[`${c.sex} age ${c.initial_age}`,c.sex,c.initial_age,c.initial_lives]);
note(sources,'G55','GSW parameters are percent; zero rates in this workbook are decimal and continuously compounded.');
set(sources,'G57',data.provenance.fed_url);
note(sources,'G59','SSA 2023 period mortality, Social Security area. Not Indian annuitants or a cohort forecast.');
set(sources,'G61',data.provenance.ssa_url);
note(sources,'G63','Faces and historical weights are imported from sealed evidence; Excel does not re-optimise them.');
sources.getRange('G69:J69').values=[['Historical input',...data.historical_cases.map(x=>x.end_month)]];header(sources,'G69:J69');
const parameterLabels=['Start curve date','End curve date','Start BETA0','Start BETA1','Start BETA2','Start BETA3','Start TAU1','Start TAU2','End BETA0','End BETA1','End BETA2','End BETA3','End TAU1','End TAU2'];
const values=data.historical_cases.map(c=>[new Date(c.start.date+'T00:00:00Z'),new Date(c.end.date+'T00:00:00Z'),...c.start.beta,c.start.tau1,c.start.tau2,...c.end.beta,c.end.tau1,c.end.tau2]);
sources.getRange('G70:J83').values=parameterLabels.map((label,j)=>[label,...values.map(x=>x[j])]);
sources.getRange('H70:J71').setNumberFormat('dd-mmm-yyyy');sources.getRange('H72:J83').setNumberFormat('0.00000000');
sources.getRange('G86:O86').values=[['Month index','Method index','Weight 1y','Weight 5y','Weight 10y','Weight 20y','Weight 30y','Initial liability PV','Sealed surplus fraction']];header(sources,'G86:O86');
sources.getRange('G87:O98').values=data.historical_cases.flatMap((c,j)=>m.map((method,k)=>[j+1,k+1,...c.methods[method].weights,c.methods[method].initial_liability_pv,c.methods[method].surplus_change_fraction]));
sources.getRange('I87:M98').setNumberFormat('0.000000');sources.getRange('N87:N98').setNumberFormat(money);sources.getRange('O87:O98').setNumberFormat('0.000000000000');
set(sources,'G104','Historical annual payment');set(sources,'H104',100);
note(sources,'G107','Historical experiment: hypothetical 30-year nominal payments and five zero bonds, reset monthly.');
note(sources,'G109','Downloaded curve history can be revised. No point-in-time-vintage or realised-profit claim.');
note(sources,'G112','Fed CSV SHA256');set(sources,'G113',data.provenance.fed_csv_sha256);
note(sources,'G116','SSA transcription SHA256');set(sources,'G117',data.provenance.ssa_transcription_sha256);
note(sources,'G120','Sealed final-prediction SHA256');set(sources,'G121',data.provenance.final_predictions_sha256);
for(const range of ['D4:D11','C15:E134','G8:K12','G16:H45','G49:J52','H70:J83','G87:O98','H104'])sources.getRange(range).format.font.color=blue;
sources.getRange('C1:C139').format.columnWidth=29;sources.getRange('F1:F139').format.columnWidth=3;
sources.getRange('G1:G139').format.columnWidth=33;
for(const col of ['H','I','J','K','L','M','N','O'])sources.getRange(`${col}1:${col}139`).format.columnWidth=20;
sources.freezePanes.freezeRows(14);

// One authoritative set of editable drivers, with validation next to each input.
controls.getRange('C3:G3').values=[['Driver','Editable value','Unit','Active input','Meaning']];header(controls,'C3:G3');
const drivers=[
 [4,'Asset portfolio',4,'1–4','1 five-year, 2 duration, 3 key rate, 4 covariance'],
 [5,'Annual benefit per life',12000,'USD','Changes liabilities; inception asset faces remain fixed'],
 [6,'Mortality force multiplier',1,'x','0.8 is lower mortality; 1.0 uses the period table'],
 [7,'Maximum paying age',120,'age','Birthday payment is retained; later payments are zero'],
 [8,'Parallel rate shift',0,'bp','Instantaneous valuation only'],
 [9,'1-year key shift',0,'bp','Linear key-rate hats, constant outside endpoint knots'],
 [10,'5-year key shift',0,'bp','Additional to the parallel shift'],
 [11,'10-year key shift',0,'bp','Additional to the parallel shift'],
 [12,'20-year key shift',0,'bp','Additional to the parallel shift'],
 [13,'30-year key shift',0,'bp','Also applies beyond 30 years'],
 [14,'Curve tail after 30 years',1,'1–3','1 Svensson, 2 flat forward, 3 flat zero'],
 [15,'Liquidation haircut',0,'fraction','Loss on gross sales; assumed, not an observed spread'],
 [16,'Cash reinvestment shift',0,'bp','Applied to cash accumulation only'],
 [17,'Runoff horizon',10,'years','Fixed ten-year schedule at initial-curve forwards'],
 [20,'Historical month',1,'1–3','1 Jan 2019, 2 Mar 2020, 3 Sep 2022']
];
for(const [r,label,value,unit,meaning] of drivers){set(controls,`C${r}`,label);set(controls,`D${r}`,value);set(controls,`E${r}`,unit);set(controls,`G${r}`,meaning);}
const bounded=(row,low,high)=>`=IF(AND(ISNUMBER(D${row}),D${row}=INT(D${row}),D${row}>=${low},D${row}<=${high}),D${row},NA())`;
form(controls,'F4',bounded(4,1,4));form(controls,'F5','=IF(AND(ISNUMBER(D5),D5>=0),D5,NA())');
form(controls,'F6','=IF(AND(ISNUMBER(D6),D6>0),D6,NA())');
form(controls,'F7',"=IF(AND(ISNUMBER(D7),D7=INT(D7),D7>MAX('Sources'!$I$49:$I$52),D7<=120),D7,NA())");
for(let r=8;r<=13;r++)form(controls,`F${r}`,`=IF(ISNUMBER(D${r}),D${r}/10000,NA())`);
form(controls,'F14',bounded(14,1,3));form(controls,'F15','=IF(AND(ISNUMBER(D15),D15>=0,D15<1),D15,NA())');
form(controls,'F16','=IF(ISNUMBER(D16),D16/10000,NA())');set(controls,'F17',10);form(controls,'F20',bounded(20,1,3));
controls.getRange('D4:D16').format={font:{color:blue},fill:light};controls.getRange('D20').format={font:{color:blue},fill:light};
controls.getRange('D5:F5').setNumberFormat(money);controls.getRange('D6:F6').setNumberFormat('0.00');controls.getRange('D15:F15').setNumberFormat('0.0%');
controls.getRange('F8:F13').setNumberFormat('0.00%');controls.getRange('F16').setNumberFormat('0.00%');
for(const [row,lo,hi] of [[4,1,4],[7,76,120],[14,1,3],[20,1,3]])controls.getRange(`D${row}`).dataValidation={rule:{type:'whole',operator:'between',formula1:lo,formula2:hi}};
controls.getRange('F4:F20').conditionalFormats.add('containsErrors',{format:{fill:'#FCE8E6',font:{color:'#9C0006',bold:true}}});
note(controls,'C23','Blue cells are editable. Invalid or missing required inputs expose an error. Zero benefit is valid.');
note(controls,'C25','Runoff uses the base Svensson curve; instantaneous rate shifts and alternative tails do not change its forward marks.');
controls.getRange('C1:C28').format.columnWidth=34;controls.getRange('D1:D28').format.columnWidth=18;
controls.getRange('E1:E28').format.columnWidth=12;controls.getRange('F1:F28').format.columnWidth=19;controls.getRange('G1:G28').format.columnWidth=79;
controls.getRange('E4:E20').format.horizontalAlignment='center';controls.getRange('G4:G20').setNumberFormat('  @');

// Current curve: separate useful Svensson loadings, base discount and active stress.
curve.getRange('C5:R5').values=[['Year','Loading 1','Exp 1','Loading 2','Exp 2','Svensson zero','Base log DF','Base DF','Active tail log DF','Rate shift','Active DF','Hat 1y','Hat 5y','Hat 10y','Hat 20y','Hat 30y']];header(curve,'C5:R5');
const curveRows=[];
for(let r=6;r<=126;r++){
 const t=`C${r}`;
 curveRows.push([r-6,
  `=IF(${t}=0,1,(1-EXP(-${t}/'Sources'!$D$10))/(${t}/'Sources'!$D$10))`,
  `=EXP(-${t}/'Sources'!$D$10)`,
  `=IF(${t}=0,1,(1-EXP(-${t}/'Sources'!$D$11))/(${t}/'Sources'!$D$11))`,
  `=EXP(-${t}/'Sources'!$D$11)`,
  `=('Sources'!$D$6+'Sources'!$D$7*D${r}+'Sources'!$D$8*(D${r}-E${r})+'Sources'!$D$9*(F${r}-G${r}))/100`,
  `=-${t}*H${r}`,`=EXP(I${r})`,
  `=IF(${t}<=30,I${r},IF(${sel(14)}=1,I${r},IF(${sel(14)}=2,$I$36+(${t}-30)*($I$36-$I$35),-${t}*$H$36)))`,
  `=${sel(8)}+N${r}*${sel(9)}+O${r}*${sel(10)}+P${r}*${sel(11)}+Q${r}*${sel(12)}+R${r}*${sel(13)}`,
  `=EXP(K${r}-${t}*L${r})`,
  `=IF(${t}<=1,1,IF(${t}<5,(5-${t})/4,0))`,
  `=IF(${t}<=1,0,IF(${t}<5,(${t}-1)/4,IF(${t}<10,(10-${t})/5,0)))`,
  `=IF(${t}<=5,0,IF(${t}<10,(${t}-5)/5,IF(${t}<20,(20-${t})/10,0)))`,
  `=IF(${t}<=10,0,IF(${t}<20,(${t}-10)/10,IF(${t}<30,(30-${t})/10,0)))`,
  `=IF(${t}<=20,0,IF(${t}<30,(${t}-20)/10,1))`]);
}
curve.getRange('C6:C126').values=curveRows.map(r=>[r[0]]);
curve.getRange('D6:R126').formulas=curveRows.map(r=>r.slice(1));
curve.getRange('D6:R126').setNumberFormat('0.000000');curve.getRange('H6:H126').setNumberFormat('0.0000%');curve.getRange('L6:L126').setNumberFormat('0.00%');
curve.getRange('C1:C128').format.columnWidth=10;curve.getRange('D1:R128').format.columnWidth=15;
for(const c of ['D','E','F','G','H','K','L'])curve.getRange(`${c}6:${c}126`).format.font.color=green;
curve.freezePanes.freezeRows(5);curve.freezePanes.freezeColumns(3);
sources.getRange('I16:I45').formulas=Array.from({length:30},(_,j)=>[`=('Curve'!H${j+7}-H${j+16})*10000`]);
sources.getRange('I16:I45').setNumberFormat('0.0000;(0.0000);0.0000');
sources.getRange('I16:I45').conditionalFormats.addCustom('ABS(I16)>0.02',{fill:'#FCE8E6',font:{color:'#9C0006',bold:true}});

// Cohort qx and survival are formula calculations, not copied expected benefits.
benefits.getRange('C5:W5').values=[['Year','Male 60 qx','Female 65 qx','Male 70 qx','Female 75 qx','Male 60 survival','Female 65 survival','Male 70 survival','Female 75 survival','Expected pay (USD)','Active DF','PV (USD)','Year × PV','Year² × PV','PV after 30 years','1y dollar duration','5y dollar duration','10y dollar duration','20y dollar duration','30y dollar duration','Base-curve PV']];header(benefits,'C5:W5');
const benefitRows=[];
for(let r=6;r<=125;r++){
 const row=[r-5];
 for(let j=0;j<4;j++){
  const age=source(6,49+j),column=j%2===0?'D':'E';
  row.push(`=IF(C${r}+${age}-1>=${sel(7)},1,INDEX('Sources'!$${column}$15:$${column}$134,C${r}+${age}))`);
 }
 for(let j=0;j<4;j++){
  const q=letter(j+1),survival=letter(j+5);
  row.push(`=${r===6?'1':survival+(r-1)}*(1-${q}${r})^${sel(6)}`);
 }
 row.push(`=${sel(5)}*(H${r}*'Sources'!$J$49+I${r}*'Sources'!$J$50+J${r}*'Sources'!$J$51+K${r}*'Sources'!$J$52)`,
  `='Curve'!M${r+1}`,`=L${r}*M${r}`,`=C${r}*N${r}`,`=C${r}*O${r}`,`=IF(C${r}>30,N${r},0)`);
 for(let j=0;j<5;j++)row.push(`=O${r}*'Curve'!${letter(11+j)}${r+1}`);
 row.push(`=L${r}*'Curve'!J${r+1}`);benefitRows.push(row);
}
benefits.getRange('C6:C125').values=benefitRows.map(r=>[r[0]]);
benefits.getRange('D6:W125').formulas=benefitRows.map(r=>r.slice(1));
section(benefits,128,'Liability and fixed asset exposures','K');
const summary=[['Liability PV (USD)','=SUM(N6:N125)'],['Duration (years)','=IF(D129=0,"n.a.",SUM(O6:O125)/D129)'],
 ['Convexity (years squared)','=IF(D129=0,"n.a.",SUM(P6:P125)/D129)'],['DV01 (USD/bp)','=SUM(O6:O125)/10000'],
 ['PV after 30 years (USD)','=SUM(Q6:Q125)'],['PV share after 30 years','=IF(D129=0,"n.a.",D133/D129)'],
 ['Expected nominal benefits','=SUM(L6:L125)'],['Fixed asset PV (USD)','=SUM(I130:I134)'],
 ['Surplus (USD)','=D136-D129'],['Funding ratio','=IF(D129=0,"n.a.",D136/D129)']];
benefits.getRange('C129:C138').values=summary.map(x=>[x[0]]);benefits.getRange('D129:D138').formulas=summary.map(x=>[x[1]]);
benefits.getRange('G129:K129').values=[['Key maturity','Liability DV01','Asset PV','Asset DV01','Net DV01']];header(benefits,'G129:K129');
for(let j=0;j<5;j++){
 const r=130+j,exposure=letter(15+j);
 set(benefits,`G${r}`,keys[j]);benefits.getRange(`H${r}:K${r}`).formulas=[[`=SUM(${exposure}6:${exposure}125)/10000`,
 `=INDEX('Sources'!$H$8:$K$12,${j+1},${sel(4)})*INDEX('Curve'!$M$6:$M$126,G${r}+1)`,
 `=I${r}*G${r}/10000`,`=J${r}-H${r}`]];
}
benefits.getRange('D6:K125').setNumberFormat('0.000000');benefits.getRange('L6:W125').setNumberFormat(money);
benefits.getRange('M6:M125').setNumberFormat('0.00000000');benefits.getRange('D129:D138').setNumberFormat(money);
benefits.getRange('D130:D131').setNumberFormat('0.000000');benefits.getRange('D134').setNumberFormat('0.0000%');benefits.getRange('D138').setNumberFormat('0.0000"x"');
benefits.getRange('H130:K134').setNumberFormat(money);
benefits.getRange('C1:C139').format.columnWidth=30;benefits.getRange('D1:W139').format.columnWidth=18;
benefits.getRange('D6:G125').format.font.color=green;benefits.getRange('L6:M125').format.font.color=green;benefits.getRange('R6:W125').format.font.color=green;
benefits.freezePanes.freezeRows(5);benefits.freezePanes.freezeColumns(3);

// Financial roll-forward: opening holdings, payments, sales, then closing assets.
runoff.getRange('C1:C60').format.columnWidth=39;runoff.getRange('D1:M60').format.columnWidth=19;
note(runoff,'C4','Base-curve forwards; expected benefits; fixed initial faces; no re-hedging.');
set(runoff,'C6','Anniversary year');runoff.getRange('D6:M6').values=[[1,2,3,4,5,6,7,8,9,10]];header(runoff,'C6:M6');
const rowLabels={8:'Opening face: 1-year zero',9:'Opening face: 5-year zero',10:'Opening face: 10-year zero',11:'Opening face: 20-year zero',12:'Opening face: 30-year zero',
 14:'Opening cash',15:'Base forward cash interest',16:'Extra reinvestment interest',18:'Maturing face amounts',19:'Cash before bond sales',
 21:'Benefits due',22:'Available bond market value',23:'Cash needed from sales',24:'Pro-rata sale fraction',25:'Gross bond sales',26:'Haircut loss',27:'Benefits paid',28:'Unpaid benefits',29:'Closing cash',
 32:'Closing face: 1-year zero',33:'Closing face: 5-year zero',34:'Closing face: 10-year zero',35:'Closing face: 20-year zero',36:'Closing face: 30-year zero',
 39:'Remaining bond market value',40:'Closing assets',41:'Remaining expected liability',42:'Unpaid benefits carried forward',43:'Surplus after unpaid benefits',
 46:'Base discount factor',47:'Cumulative discounted benefits paid',48:'Cumulative discounted haircut losses',49:'Cumulative discounted extra interest',50:'Initial assets at base curve',51:'Discounted wealth difference',
 54:'Forward mark factor: 1-year zero',55:'Forward mark factor: 5-year zero',56:'Forward mark factor: 10-year zero',57:'Forward mark factor: 20-year zero',58:'Forward mark factor: 30-year zero'};
for(const [r,label] of Object.entries(rowLabels))set(runoff,`C${r}`,label);
for(let j=0;j<10;j++){
 const c=letter(j+1),prior=letter(j),year=`${c}$6`;
 for(let k=0;k<5;k++){
  form(runoff,`${c}${8+k}`,j===0?`=INDEX('Sources'!$H$8:$K$12,${k+1},${sel(4)})`:`=${prior}${32+k}`);
  form(runoff,`${c}${32+k}`,`=IF('Sources'!$G$${8+k}<=${year},0,${c}${8+k}*(1-${c}24))`);
  form(runoff,`${c}${54+k}`,`=IF('Sources'!$G$${8+k}>${year},INDEX('Curve'!$J$6:$J$126,'Sources'!$G$${8+k}+1)/${c}46,0)`);
 }
 const f={
 14:j===0?'=0':`=${prior}29`,
 15:`=${c}14*(INDEX('Curve'!$J$6:$J$126,${year})/${c}46-1)`,
 16:`=${c}14*INDEX('Curve'!$J$6:$J$126,${year})/${c}46*(EXP(${sel(16)})-1)`,
 18:`=SUMIFS(${c}8:${c}12,'Sources'!$G$8:$G$12,${year})`,
 19:`=SUM(${c}14:${c}16,${c}18)`,
 21:`=INDEX('Benefits'!$L$6:$L$125,${year})`,
 22:`=SUMPRODUCT(${c}8:${c}12,${c}54:${c}58)`,23:`=MAX(${c}21-${c}19,0)`,
 24:`=IF(${c}22>0,MIN(${c}23/((1-${sel(15)})*${c}22),1),0)`,
 25:`=${c}22*${c}24`,26:`=${c}25*${sel(15)}`,27:`=MIN(${c}21,${c}19+${c}25-${c}26)`,
 28:`=MAX(${c}21-${c}27,0)`,29:`=MAX(${c}19+${c}25-${c}26-${c}27,0)`,
 39:`=SUMPRODUCT(${c}32:${c}36,${c}54:${c}58)`,40:`=SUM(${c}29,${c}39)`,
 41:`=SUMIFS('Benefits'!$W$6:$W$125,'Benefits'!$C$6:$C$125,">"&${year})/${c}46`,
 42:j===0?`=${c}28`:`=${prior}42*${prior}46/${c}46+${c}28`,43:`=${c}40-${c}41-${c}42`,
 46:`=INDEX('Curve'!$J$6:$J$126,${year}+1)`,
 47:`=${j===0?'0':prior+'47'}+${c}27*${c}46`,48:`=${j===0?'0':prior+'48'}+${c}26*${c}46`,49:`=${j===0?'0':prior+'49'}+${c}16*${c}46`,
 50:j===0?`=SUM(${keys.map((_,k)=>`D${8+k}*INDEX('Curve'!$J$6:$J$126,'Sources'!$G$${8+k}+1)`).join(',')})`:'=$D$50',
 51:`=${c}50+${c}49-${c}47-${c}48-${c}40*${c}46`
 };
 for(const [r,value] of Object.entries(f))form(runoff,`${c}${r}`,value);
}
runoff.getRange('D8:M58').setNumberFormat(money);
for(const r of [24,46,54,55,56,57,58])runoff.getRange(`D${r}:M${r}`).setNumberFormat(r===24?'0.0000%':'0.00000000');
for(const r of [19,29,40,43])runoff.getRange(`C${r}:M${r}`).format={fill:light,font:{bold:true,color:navy},borders:{top:{style:'thin',color:'#B9C5CF'}}};
runoff.getRange('D51:M51').setNumberFormat('[>=0.005]0.00;[<=-0.005](0.00);0.00');
runoff.getRange('D51:M51').conditionalFormats.addCustom('ABS(D51)>0.0001',{fill:'#FCE8E6',font:{color:'#9C0006',bold:true}});
runoff.freezePanes.freezeRows(6);runoff.freezePanes.freezeColumns(3);

// Reprice three actual observed one-month experiments; aggregate all84 final months.
historical.getRange('C1:C149').format.columnWidth=27;historical.getRange('D1:N149').format.columnWidth=18;
set(historical,'C6','Starting curve date');set(historical,'C7','Ending curve date');set(historical,'C8','Actual elapsed years');
form(historical,'D6',`=INDEX('Sources'!$H$70:$J$70,1,${sel(20)})`);form(historical,'D7',`=INDEX('Sources'!$H$71:$J$71,1,${sel(20)})`);form(historical,'D8','=(D7-D6)/365.25');historical.getRange('D6:D7').setNumberFormat('dd-mmm-yyyy');historical.getRange('D8').setNumberFormat('0.00000000');
for(let j=0;j<6;j++){
 set(historical,`G${6+j}`,j<4?'Start BETA'+j:'Start TAU'+(j-3));form(historical,`H${6+j}`,`=INDEX('Sources'!$H$${72+j}:$J$${72+j},1,${sel(20)})`);
 set(historical,`J${6+j}`,j<4?'End BETA'+j:'End TAU'+(j-3));form(historical,`K${6+j}`,`=INDEX('Sources'!$H$${78+j}:$J$${78+j},1,${sel(20)})`);
}
historical.getRange('H6:K11').setNumberFormat('0.00000000');
historical.getRange('C14:I14').values=[['Maturity','Imported weight','Start DF','Face amount','Rolled end DF','End asset PV','Initial asset PV']];header(historical,'C14:I14');
const index=`((${sel(20)}-1)*4+${sel(4)})`;
for(let j=0;j<5;j++){
 const r=15+j;
 set(historical,`C${r}`,keys[j]);historical.getRange(`D${r}:I${r}`).formulas=[[`=INDEX('Sources'!$I$87:$M$98,${index},${j+1})`,
  `=INDEX($E$28:$E$57,C${r})`,`=$D$22*D${r}/E${r}`,`=INDEX($H$28:$H$57,C${r})`,`=F${r}*G${r}`,`=F${r}*E${r}`]];
}
for(const [c,label,f] of [['C22','Initial liability PV','=SUM(I28:I57)'],['C23','End liability PV','=SUM(J28:J57)'],['G22','End asset PV','=SUM(H15:H19)'],['G23','Surplus fraction','=(H22-D23)/D22'],['G24','Sealed surplus fraction',`=INDEX('Sources'!$O$87:$O$98,${index})`],['G25','Repricing difference','=H23-H24']]){
 set(historical,c,label);form(historical,c.replace(/[CG]/,x=>x==='C'?'D':'H'),f);
}
historical.getRange('C27:J27').values=[['Maturity','Start zero','Start DF','Rolled maturity','End zero','End DF','Start liability PV','End liability PV']];header(historical,'C27:J27');
function svenssonFormula(t,b0,b1,b2,b3,t1,t2){const a1=`((1-EXP(-${t}/${t1}))/(${t}/${t1}))`,a2=`((1-EXP(-${t}/${t2}))/(${t}/${t2}))`;return `(${b0}+${b1}*${a1}+${b2}*(${a1}-EXP(-${t}/${t1}))+${b3}*(${a2}-EXP(-${t}/${t2})))/100`;}
const historicRows=[];
for(let r=28;r<=57;r++)historicRows.push([r-27,`=${svenssonFormula('C'+r,'$H$6','$H$7','$H$8','$H$9','$H$10','$H$11')}`,`=EXP(-C${r}*D${r})`,`=C${r}-$D$8`,
 `=${svenssonFormula('F'+r,'$K$6','$K$7','$K$8','$K$9','$K$10','$K$11')}`,`=EXP(-F${r}*G${r})`,`='Sources'!$H$104*E${r}`,`='Sources'!$H$104*H${r}`]);
historical.getRange('C28:C57').values=historicRows.map(r=>[r[0]]);
historical.getRange('D28:J57').formulas=historicRows.map(r=>r.slice(1));
historical.getRange('D28:D57').setNumberFormat('0.0000%');historical.getRange('G28:G57').setNumberFormat('0.0000%');
historical.getRange('E28:F57').setNumberFormat('0.00000000');historical.getRange('H28:H57').setNumberFormat('0.00000000');historical.getRange('I28:J57').setNumberFormat(money);
historical.getRange('D15:I19').setNumberFormat('0.00000000');historical.getRange('D22:D23').setNumberFormat(money);historical.getRange('H22').setNumberFormat(money);historical.getRange('H23:H25').setNumberFormat('0.000000000000');
historical.getRange('H25').format.font.color=ink;
note(historical,'C60','Sealed final predictions below are inputs. The RMSE aggregation is recalculated; weights are not re-optimised.');
historical.getRange('C62:G62').values=[['End month',...labels]];header(historical,'C62:G62');
historical.getRange('C63:G146').values=data.final_prediction_table.map(row=>[new Date(row[0]+'-01T00:00:00Z'),...row.slice(1)]);
historical.getRange('C63:C146').setNumberFormat('mmm-yy');historical.getRange('D63:G146').setNumberFormat('0.0000000000');historical.getRange('C63:G146').format.font.color=blue;
historical.getRange('L15:N15').values=[['Method','RMSE (bp)','Bias (bp)']];header(historical,'L15:N15');
for(let j=0;j<4;j++){
 const c=letter(j+1),r=16+j;
 set(historical,`L${r}`,labels[j]);form(historical,`M${r}`,`=SQRT(SUMSQ(${c}63:${c}146)/84)*10000`);form(historical,`N${r}`,`=AVERAGE(${c}63:${c}146)*10000`);
}
historical.getRange('M16:N19').setNumberFormat('0.0000');
note(historical,'L22','84 final months, Jan 2019 to Dec 2025.');
note(historical,'L24','RMSE units: bp of initial liability PV.');
note(historical,'L26','Retrospective reset-portfolio experiments.');
historical.getRange('L1:L149').format.columnWidth=23;
historical.getRange('G1:G149').format.columnWidth=25;
historical.freezePanes.freezeRows(3);

// Primary view links to the owning builds. It does not read terminal checks.
review.getRange('C1:C42').format.columnWidth=34;review.getRange('D1:D42').format.columnWidth=21;
review.getRange('E1:E42').format.columnWidth=3;review.getRange('F1:F42').format.columnWidth=3;
review.getRange('G1:G42').format.columnWidth=36;review.getRange('H1:H42').format.columnWidth=22;
set(review,'C3','Current curve date');form(review,'D3',"='Sources'!D4");review.getRange('D3').setNumberFormat('dd-mmm-yyyy');
set(review,'G3','Selected fixed portfolio');form(review,'H3',`=INDEX('Sources'!$H$7:$K$7,1,${sel(4)})`);review.getRange('H3').format.font.color=green;
section(review,5,'Instantaneous balance sheet','D');set(review,'G5','Ten-year expected runoff');review.getRange('G5:H5').format={fill:light,font:{name:'Arial',size:10,bold:true,color:navy},rowHeight:24};
const primary=[['C7','Liability PV (USD)',"='Benefits'!D129"],['C8','Fixed asset PV (USD)',"='Benefits'!D136"],['C9','Surplus (USD)',"='Benefits'!D137"],
 ['C11','Liability duration (years)',"='Benefits'!D130"],['C12','DV01 (USD/bp)',"='Benefits'!D132"],['C13','Convexity (years squared)',"='Benefits'!D131"],['C14','PV after 30 years',"='Benefits'!D134"],
 ['G7','Gross bond sales (USD)',"=SUM('Runoff'!D25:M25)"],['G8','Nominal haircut losses (USD)',"=SUM('Runoff'!D26:M26)"],['G9','Nominal benefits unpaid (USD)',"=SUM('Runoff'!D28:M28)"],
 ['G11','Year 10 assets (USD)',"='Runoff'!M40"],['G12','Year 10 expected liability (USD)',"='Runoff'!M41"],['G13','Year 10 unpaid carried (USD)',"='Runoff'!M42"],['G14','Year 10 surplus after unpaid (USD)',"='Runoff'!M43"]];
for(const [cell,label,f] of primary){set(review,cell,label);form(review,cell.replace(/[CG]/,x=>x==='C'?'D':'H'),f);}
review.getRange('D7:D14').setNumberFormat(money);review.getRange('H7:H14').setNumberFormat(money);review.getRange('D11').setNumberFormat('0.000000');review.getRange('D13').setNumberFormat('0.000000');review.getRange('D14').setNumberFormat('0.0000%');
review.getRange('D9').format.font={bold:true,size:12,color:navy};review.getRange('H14').format.font={bold:true,size:12,color:navy};
review.getRange('C17:D17').values=[['Key maturity','Liability DV01']];review.getRange('G17:H17').values=[['Asset DV01','Net DV01']];header(review,'C17:D17');header(review,'G17:H17');
for(let j=0;j<5;j++){
 review.getRange(`C${18+j}:D${18+j}`).formulas=[[`='Benefits'!G${130+j}`,`='Benefits'!H${130+j}`]];
 review.getRange(`G${18+j}:H${18+j}`).formulas=[[`='Benefits'!J${130+j}`,`='Benefits'!K${130+j}`]];
}
review.getRange('D18:D22').setNumberFormat(money);review.getRange('G18:H22').setNumberFormat(money);
note(review,'C24','Key-rate exposures are USD per 1 bp shift at the named maturity.');
set(review,'C26','Final historical RMSE (bp)');form(review,'D26',`=INDEX('Historical'!$M$16:$M$19,${sel(4)})`);review.getRange('D26').setNumberFormat('0.0000');
set(review,'G26','Monthly surplus fraction');form(review,'H26',"='Historical'!H23");review.getRange('H26').setNumberFormat('0.000000000000');
note(review,'C28','Historical RMSE uses 84 final months. The monthly example reprices the selected dates independently.');
note(review,'C30','Synthetic USD benefits. Lower mortality raises expected benefits; the rate hedge does not cover longevity.');
note(review,'C32','Use Controls for rates, mortality, liquidation and cash reinvestment assumptions. Faces stay fixed.');
note(review,'C34','Instantaneous shocks revalue both sides. Runoff retains the base curve\u2019s deterministic forwards.');
note(review,'C36','Haircuts and cash-rate shifts are scenarios. No shortfall probability or actual trading profit is estimated.');
note(review,'C38','The default portfolio was selected on historical development months, before final scoring.');
for(const range of ['C7:D9','G11:H14'])review.getRange(range).format.borders={bottom:{style:'thin',color:'#CAD3DB'}};

// Reconciliation uses actual formula evaluation after each control change.
wb.recalculate();
let comparisons=0,maxFinancial=0,maxFraction=0;
const toleranceUSD=.0001,toleranceFraction=2e-12;
function close(actual,expected,label,tolerance=toleranceUSD){
 if(typeof actual!=='number'||!Number.isFinite(actual))throw Error(`${label}: nonnumeric ${actual}`);
 const delta=Math.abs(actual-expected);comparisons++;
 if(tolerance===toleranceUSD)maxFinancial=Math.max(maxFinancial,delta);else maxFraction=Math.max(maxFraction,delta);
 if(delta>tolerance)throw Error(`${label}: ${actual} vs ${expected}, difference ${delta}`);
}
const defaults={4:4,5:12000,6:1,7:120,8:0,9:0,10:0,11:0,12:0,13:0,14:1,15:0,16:0,20:1};
function change(updates){const active={...defaults,...updates};controls.getRange('D4:D16').values=Array.from({length:13},(_,j)=>[active[j+4]]);set(controls,'D20',active[20]);wb.recalculate();}
const value=(s,c)=>s.getRange(c).values[0][0];
for(let j=0;j<4;j++){
 const expected=data.historical_final_reference.final_scores[m[j]];
 close(value(historical,`M${16+j}`),expected.rmse*10000,'Historical RMSE '+m[j],1e-10);
 close(value(historical,`N${16+j}`),expected.bias*10000,'Historical bias '+m[j],1e-10);
}
for(let j=0;j<30;j++)close(value(sources,`I${j+16}`),0,'Published current zero '+(j+1),.02);
const instantChecks=[];
for(const expected of data.current_reference.instantaneous_scenarios){
 const updates={...defaults,4:m.indexOf(expected.method)+1,6:expected.mortality_force,7:expected.maximum_paying_age,
 8:expected.parallel_shift_decimal*10000,14:['svensson','flat_forward','flat_zero'].indexOf(expected.tail)+1};
 expected.key_shifts_decimal.forEach((v,j)=>updates[9+j]=v*10000);change(updates);
 close(value(benefits,'D129'),expected.liability_usd,'Instant liability '+expected.scenario);
 close(value(benefits,'D136'),expected.assets_usd,'Instant asset '+expected.scenario);
 close(value(benefits,'D137'),expected.surplus_usd,'Instant surplus '+expected.scenario);
 instantChecks.push({scenario:expected.scenario,method:expected.method,liability_usd:value(benefits,'D129'),surplus_usd:value(benefits,'D137')});
}
console.log(JSON.stringify({stage:'instantaneous reconciliation',cases:instantChecks.length}));
const map={14:'opening_cash_usd',15:'base_cash_interest_usd',16:'extra_cash_interest_usd',18:'maturities_usd',21:'benefits_due_usd',25:'gross_bond_sales_usd',26:'haircut_cost_usd',27:'benefits_paid_usd',28:'unpaid_benefits_usd',29:'closing_cash_usd',39:null,40:'assets_usd',41:'remaining_liability_usd',42:'unpaid_forward_carried_usd',43:'surplus_after_unpaid_usd',51:'discounted_wealth_conservation_error_usd'};
for(let k=0;k<5;k++)map[32+k]=`remaining_face_${keys[k]}y_usd`;
const runoffChecks=[];
for(const expected of data.current_reference.runoff_scenarios){
 change({...defaults,4:m.indexOf(expected.method)+1,6:expected.mortality_force,15:expected.haircut,16:expected.cash_rate_shift_decimal*10000});
 const grid=runoff.getRange('D8:M58').values;
 for(let year=0;year<10;year++)for(const [r,field] of Object.entries(map))if(field)close(grid[Number(r)-8][year],expected.annual_rows[year][field],`Runoff ${expected.case_id}/${year+1}/${field}`);
 close(value(review,'H7'),expected.gross_bond_sales_usd,'Gross sales');close(value(review,'H8'),expected.haircut_cost_usd,'Haircut losses');
 close(value(review,'H9'),expected.unpaid_nominal_usd,'Unpaid benefits');
 runoffChecks.push({case_id:expected.case_id,method:expected.method,force:expected.mortality_force,haircut:expected.haircut,cash_shift:expected.cash_rate_shift_decimal,final_surplus_usd:value(review,'H14')});
 if(runoffChecks.length%36===0)console.log(JSON.stringify({stage:'runoff reconciliation',cases:runoffChecks.length}));
}
const historicalChecks=[];
for(let month=0;month<3;month++)for(let j=0;j<4;j++){
 change({...defaults,4:j+1,20:month+1});const expected=data.historical_cases[month].methods[m[j]];
 close(value(historical,'D22'),expected.initial_liability_pv,'Historical initial PV',1e-9);
 close(value(historical,'H23'),expected.surplus_change_fraction,'Historical rolled surplus',toleranceFraction);
 historicalChecks.push({month:data.historical_cases[month].end_month,method:m[j],surplus_fraction:value(historical,'H23')});
}
change(defaults);
const risk=data.current_reference.base_liability_risk;
close(value(benefits,'D130'),risk.duration,'Duration',1e-10);close(value(benefits,'D131'),risk.convexity,'Convexity',1e-9);
close(value(benefits,'D132'),risk.dv01_usd,'DV01');close(value(benefits,'D133'),risk.post30_pv_usd,'Post30 PV');
for(let j=0;j<5;j++)close(value(benefits,`H${130+j}`),risk.key_dv01_usd[j],'Key DV01');
change({...defaults,5:0});if(value(benefits,'D129')!==0||value(benefits,'D130')!=='n.a.')throw Error('Zero-benefit boundary failed.');
controls.getRange('D5').clear({applyTo:'contents'});wb.recalculate();if(typeof value(benefits,'D129')==='number')throw Error('Missing benefit hidden as a number.');
change({...defaults,6:0});if(typeof value(benefits,'D129')==='number')throw Error('Zero mortality force accepted.');
change({...defaults,15:1});if(typeof value(runoff,'M43')==='number')throw Error('100% haircut accepted.');
change(defaults);
// Invalid unused historical selector must not affect the independent current valuation.
controls.getRange('D20').clear({applyTo:'contents'});wb.recalculate();
close(value(benefits,'D129'),risk.pv,'Independent current model after missing historical selector');
if(typeof value(historical,'H23')==='number')throw Error('Missing historical selector was silently accepted.');
change(defaults);
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:50},maxChars:4000});
if(/"matchCount":\s*[1-9]|"matches":\s*\[\s*\{/.test(errors.ndjson))throw Error('Unexpected formula error: '+errors.ndjson);
const inspection=await wb.inspect({kind:'table',range:"'ALM review'!C7:H14",include:'values,formulas',tableMaxRows:8,tableMaxCols:6,maxChars:2500});
console.log(inspection.ndjson);console.log('ERROR_SCAN',errors.ndjson);
const renderRanges=[['ALM review','C1:H39','review'],['Controls','C1:G26','controls'],['Benefits','C1:N16','benefits'],['Benefits','C128:K138','risk'],['Curve','C1:R15','curve'],['Runoff','C1:M29','runoff_cash'],['Runoff','C32:M58','runoff_assets'],['Historical','C1:N28','historical'],['Historical','C132:G146','historical_tail'],['Sources','C1:K24','sources'],['Sources','G48:O63','source_context'],['Sources','G69:O98','historical_sources']];
for(const [sheetName,range,name] of renderRanges){
 const blob=await wb.render({sheetName,range,scale:1.2,format:'png'});
 await fs.writeFile(path.join(output,name+'.png'),new Uint8Array(await blob.arrayBuffer()));
}
const filename='Treasury_ALM_Reconciliation.xlsx';
const exported=await SpreadsheetFile.exportXlsx(wb);await exported.save(path.join(output,filename));
// Import the actual saved file, recalculate, then change an input in that copy.
const reopened=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(output,filename)));
reopened.recalculate();
close(reopened.worksheets.getItem('Benefits').getRange('D129').values[0][0],risk.pv,'Saved/reopened default valuation');
reopened.worksheets.getItem('Controls').getRange('D6').values=[[.8]];reopened.recalculate();
const lowerMortality=data.current_reference.instantaneous_scenarios.find(x=>x.method==='covariance'&&x.scenario==='mortality_force_0.8');
close(reopened.worksheets.getItem('Benefits').getRange('D129').values[0][0],lowerMortality.liability_usd,'Saved/reopened mortality recalculation');
const receipt={status:'numeric checks passed; visual review recorded separately',input_sha256:crypto.createHash('sha256').update(raw).digest('hex'),
 engine:'Artifact Tool formula engine; saved XLSX reimport/recalculation checked; native desktop Excel not tested',
 sheets:names,financial_absolute_tolerance_usd:toleranceUSD,historical_surplus_fraction_tolerance:toleranceFraction,
 maximum_financial_difference_usd:maxFinancial,numeric_comparisons:comparisons,
 instantaneous_cases:instantChecks.length,runoff_cases:runoffChecks.length,runoff_annual_records:1080,
 historical_month_portfolio_repricing_cases:historicalChecks.length,historical_rmse_candidates:4,current_quoted_zeros_reconciled:30,
 zero_benefit_preserved:true,missing_benefit_exposes_error:true,invalid_force_and_haircut_expose_error:true,
 unrelated_missing_historical_selector_does_not_gate_current_model:true,defaults_restored_before_export:true,
 saved_file_recalculation_and_input_change_passed:true,error_scan:errors.ndjson,
 source_observations_and_frozen_model_outcomes_changed:false,
 weights_and_faces_imported_not_optimised_in_spreadsheet:true,
 renders:renderRanges.map(([sheet,range,name])=>({sheet,range,file:name+'.png'})),
 instantaneous_reconciliations:instantChecks,runoff_reconciliations:runoffChecks,historical_reconciliations:historicalChecks,
 workbook_sha256:crypto.createHash('sha256').update(await fs.readFile(path.join(output,filename))).digest('hex')};
await fs.writeFile(path.join(output,'workbook_numeric_verification.json'),JSON.stringify(receipt,null,2)+'\n');
console.log(JSON.stringify({stage:'exported and reopened',file:path.join(output,filename),numeric_comparisons:comparisons,maximum_financial_difference_usd:maxFinancial}));
