"""Scientific plot: fitted reconstruction and distinct rolling nowcast errors."""
import argparse,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

def main(a):
    b=json.loads((a.evidence/'observed_rows.json').read_text());metrics=json.loads((a.evidence/'metrics.json').read_text())
    curve=[r for r in json.loads((a.evidence/'curve.json').read_text()) if r['is_daily'] and r['with_sensors']]
    t=pd.to_datetime([r['at'] for r in curve]);q=[r['with_sensors'] for r in curve]
    mean=[r['predicted_mean_weight_g'] for r in q];lo=[r['conditional_95_lower_g'] for r in q];hi=[r['conditional_95_upper_g'] for r in q]
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10.5,'axes.spines.top':False,'axes.spines.right':False})
    fig=plt.figure(figsize=(14,8),facecolor='#f6f8fa')
    gs=fig.add_gridspec(1,2,left=.065,right=.97,top=.73,bottom=.285,wspace=.42,width_ratios=[1.8,1])
    ax=fig.add_subplot(gs[0]);ax.set_facecolor('white')
    ax.fill_between(t,lo,hi,color='#2c807b',alpha=.18,label='Banda condicional GP del 95%*')
    ax.plot(t,mean,color='#237b75',lw=2.5,label='Gaussiano con sensores')
    ax.plot(t,[r['time_only']['predicted_mean_weight_g'] for r in curve],color='#cc6a2e',ls='--',lw=1.4,label='Gaussiano solo con tiempo')
    ax.errorbar(pd.to_datetime([r['date'] for r in b],utc=True),[r['weight_g'] for r in b],
      yerr=[r['sample_se_g'] for r in b],fmt='o',ms=6,color='#18333f',capsize=4,label='7 pesos medidos ± 1 error estándar')
    ax.xaxis.set_major_locator(mdates.MonthLocator());ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    ax.set_ylabel('Peso medio del lote (g)');ax.set_xlabel('Fecha · 2026');ax.grid(axis='y',alpha=.17)
    ax.set_title('Curva reconstruida entre los pesajes',loc='left',fontweight='bold',pad=15,fontsize=12)
    ax.legend(loc='upper left',frameon=False,fontsize=8.6)
    ax2=fig.add_subplot(gs[1]);ax2.set_facecolor('white')
    vals=[metrics['gp_with_sensors']['MAE_g'],metrics['gp_time_only']['MAE_g'],metrics['recent_trend_g']['MAE_g']]
    ax2.barh(range(3),vals,color=['#237b75','#cc6a2e','#8797a0'],height=.55)
    ax2.set_yticks(range(3),['Gaussiano\ncon sensores','Gaussiano\nsolo tiempo','Tendencia\nreciente']);ax2.invert_yaxis();ax2.set_xlim(0,22)
    for i,v in enumerate(vals):ax2.text(v+.35,i,f'{v:.2f} g'.replace('.',','),va='center',fontweight='bold')
    ax2.set_xlabel('Error medio (g) · menor es mejor');ax2.grid(axis='x',alpha=.15);ax2.set_axisbelow(True)
    ax2.set_title('Comprobación en 4 fechas',loc='left',fontweight='bold',pad=15,fontsize=12)
    fig.text(.065,.93,'Modelo gaussiano entrenado con las biometrías de MySQL',fontsize=21,fontweight='bold',color='#18333f')
    fig.text(.065,.876,'Un único ML: tiempo + historial medido de temperatura, oxígeno y pH → peso medio estimado.',fontsize=12,color='#455864')
    fig.text(.065,.826,'3.259 puntos horarios y diarios estimados; ninguno se utilizó como una nueva etiqueta de entrenamiento.',fontsize=11,color='#455864')
    fig.text(.065,.191,'Los sensores redujeron el error solo 0,11 g: su aporte todavía no es concluyente.',fontsize=13,fontweight='bold',color='#18333f')
    fig.text(.065,.14,'Izquierda: ajuste final con las 7 biometrías, incluidas las posteriores a cada punto; es reconstrucción retrospectiva.\nDerecha: estimaciones al 07/08, 13/09, 26/09 y 16/10, ajustadas solo con pesos anteriores y sensores hasta la fecha objetivo.\nEs nowcast, no pronóstico previo. Fechas ya conocidas de un lote; *banda GP condicional sin calibración externa, no pesos individuales.',
      fontsize=10,color='#455864',va='top',linespacing=1.6)
    a.output.parent.mkdir(parents=True,exist_ok=True);fig.savefig(a.output,dpi=180,facecolor=fig.get_facecolor());plt.close(fig)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path,required=True);p.add_argument('--output',type=Path,required=True);main(p.parse_args())
