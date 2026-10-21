"""Scientific reference plots: observed distributions, never synthetic growth."""
import csv
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE=Path(__file__).resolve().parent


def main():
    fish=list(csv.DictReader((HERE/'data/kamble_2024_endpoint_samples.csv').open()))
    garcia=list(csv.DictReader((HERE/'data/garcia_2012_observed_weekly_means.csv').open()))
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False})
    fig,ax=plt.subplots(1,2,figsize=(13,6))
    fig.subplots_adjust(left=.065,right=.98,bottom=.21,top=.80,wspace=.26)
    colors=['#397c9c','#bc6c25']
    bins=np.arange(0,121,10)
    for endpoint,label,color in zip(('initial','final'),('Inicio, n=75','Día 60, n=75'),colors):
        w=[float(r['weight_g']) for r in fish if r['treatment']=='Control' and r['endpoint']==endpoint]
        ax[0].hist(w,bins=bins,histtype='step',linewidth=2.4,color=color,label=label)
    ax[0].set(title='Distribuciones observadas: un tratamiento',xlabel='Peso individual (g)',ylabel='Número de mediciones')
    ax[0].legend(frameon=False)
    ax[0].set_ylim(0,60)
    ax[0].text(.02,.88,'Muestras de 3 tanques; no se asume\nidentidad individual entre fechas.',transform=ax[0].transAxes,fontsize=9)
    ax[1].plot([int(r['days_since_first_sample']) for r in garcia],[float(r['mean_weight_g']) for r in garcia],
        marker='o',markersize=4,color='#397c9c',linewidth=1.7)
    ax[1].set(title='Trayectoria observada: Piura, 2011',xlabel='Días desde la primera biometría publicada',ylabel='Peso medio (g)')
    ax[1].text(.04,.88,'22 fechas, una cohorte.\nNo es un estándar mundial.',transform=ax[1].transAxes,fontsize=10)
    for a in ax:a.grid(axis='y',alpha=.15)
    fig.suptitle('Referencias de crecimiento de tilapia: dos escalas de evidencia',fontsize=16,fontweight='bold')
    fig.text(.065,.04,'Fuentes: Kamble et al., Zenodo 11174309, tablas 8-14 (CC BY 4.0); García et al. (2012), tabla 1.\nNo se generaron pesos intermedios. Los puntos de Piura son medias, no mediciones individuales.',fontsize=9)
    (HERE/'figures').mkdir(exist_ok=True)
    fig.savefig(HERE/'figures/referencias_observadas.png',dpi=180,bbox_inches='tight')
    plt.close(fig)


if __name__=='__main__':main()
