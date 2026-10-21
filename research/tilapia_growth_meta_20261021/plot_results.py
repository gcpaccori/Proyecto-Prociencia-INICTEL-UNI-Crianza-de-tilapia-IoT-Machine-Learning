"""Scientific plot of development results, including failed horizons."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

p=argparse.ArgumentParser()
p.add_argument('--evidence',type=Path,required=True)
p.add_argument('--old-results',type=Path,required=True)
p.add_argument('--out',type=Path,required=True)
args=p.parse_args();args.out.mkdir(parents=True,exist_ok=True)
local=pd.read_csv(args.evidence/'local_predictions.csv')
old=pd.read_csv(args.old_results)
old=old[(old['mode']=='rolling_origin')&(old.model=='selected_reconstruction')]
merged=local.merge(old[['target_date','predicted_g']],on='target_date',validate='one_to_one')
merged['target_date']=pd.to_datetime(merged.target_date)
external=json.loads((args.evidence/'external_by_horizon.json').read_text())
novel=merged.iloc[1:]
maes=[float(np.mean(abs(novel[k]-novel.actual))) for k in ['prediction','predicted_g','trend']]
ink,blue,orange,grey,green='#193b4a','#157b96','#d18a20','#7d8a96','#307e64'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10.5,'text.color':ink,
    'axes.labelcolor':ink,'axes.titlecolor':ink,'axes.spines.top':False,'axes.spines.right':False})
fig=plt.figure(figsize=(13,11),facecolor='white')
grid=fig.add_gridspec(2,2,height_ratios=[1.2,1],left=.075,right=.97,bottom=.13,top=.82,hspace=.58,wspace=.32)
fig.text(.075,.965,'Mejora aplicada: ML con historia biométrica',fontsize=24,fontweight='bold',va='top')
fig.text(.075,.92,'Extra Trees aprende la tasa futura usando peso, duración y crecimiento previo.',fontsize=13,va='top')
fig.text(.075,.884,'Evaluación retrospectiva de desarrollo: las biometrias y las referencias externas ya eran conocidas.',fontsize=10.5,color=grey,va='top')
ax=fig.add_subplot(grid[0,:]);ax.set_title('1. Peso observado y pronósticos con biometrias anteriores',loc='left',fontweight='bold',pad=14)
ax.plot(merged.target_date,merged.actual,'o-',color=ink,label='Peso observado',lw=2.5,markersize=7)
ax.plot(merged.target_date,merged.prediction,'X--',color=blue,label='Extra Trees nuevo',lw=2,markersize=8)
ax.plot(merged.target_date,merged.predicted_g,'s:',color=orange,label='RF anterior',lw=1.8,markersize=5)
ax.plot(merged.target_date,merged.trend,'d:',color=grey,label='Tendencia reciente',lw=1.8,markersize=5)
ax.set_xticks(merged.target_date,merged.target_date.dt.strftime('%d/%m'));ax.set_ylim(65,165);ax.set_ylabel('Peso medio (g)')
ax.grid(axis='y',alpha=.16);ax.legend(loc='upper left',frameon=False,ncol=2,fontsize=9)
ax.text(.01,.02,'El error de agosto sigue siendo alto: 28,95 g. El 11/07 se excluye del resumen inferior.',transform=ax.transAxes,fontsize=9,color=grey)
ax=fig.add_subplot(grid[1,0]);ax.set_title('2. Error local en las mismas cuatro fechas',loc='left',fontweight='bold',pad=14)
bars=ax.bar(['Extra Trees','RF anterior','Tendencia'],maes,color=[blue,orange,grey],width=.6)
for bar,v in zip(bars,maes):ax.text(bar.get_x()+bar.get_width()/2,v+.4,f'{v:.2f} g',ha='center',fontweight='bold')
ax.set_ylabel('Error absoluto medio (g)');ax.set_ylim(0,max(maes)*1.3);ax.grid(axis='y',alpha=.16);ax.set_axisbelow(True)
ax=fig.add_subplot(grid[1,1]);ax.set_title('3. Desarrollo externo: no gana siempre',loc='left',fontweight='bold',pad=14)
xx=np.arange(4);width=.33
for shift,study,label,color in [(-.5,'piura','Piura',green),(.5,'saudi','Arabia Saudita',blue)]:
    q=sorted([r for r in external if r['study']==study],key=lambda r:r['horizon_days'])
    vals=[r['MAE_g']/r['recent_trend_MAE_g'] for r in q]
    ax.bar(xx+shift*width,vals,width,label=label,color=color)
ax.axhline(1,color=orange,lw=1.6,ls='--');ax.set_ylim(0,1.9)
ax.set_xticks(xx,['7 días','14 días','21 días','28 días']);ax.set_ylabel('MAE del ML / MAE de tendencia')
ax.text(.02,.94,'Menos de 1 = mejora; más de 1 = empeora',transform=ax.transAxes,fontsize=9,color=grey)
ax.legend(frameon=False,fontsize=9,loc='upper right',bbox_to_anchor=(1,.9));ax.grid(axis='y',alpha=.16);ax.set_axisbelow(True)
fig.text(.075,.075,f'MAE local: {maes[0]:.2f} g. Mejora de {(1-maes[0]/maes[1])*100:.1f}% frente al RF y {(1-maes[0]/maes[2])*100:.1f}% frente a tendencia.',fontsize=11,fontweight='bold')
fig.text(.075,.045,'Una campaña local, cuatro fechas; estudios usados para selección. No acredita precisión futura ni un efecto aprendido de luz/sensores.',fontsize=10,color=grey)
fig.savefig(args.out/'Tilapia_Mejora_ML_Aplicada_2026-10-21.png',dpi=175)
merged.to_csv(args.out/'Comparacion_Local_ML_2026-10-21.csv',index=False)
print(args.out/'Tilapia_Mejora_ML_Aplicada_2026-10-21.png')
