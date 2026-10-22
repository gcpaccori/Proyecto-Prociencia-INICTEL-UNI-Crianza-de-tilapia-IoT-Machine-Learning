"""Read-only consistent snapshot of one pond/cohort; run inside trusted backend.

Credentials stay in the existing backend settings. Dates retain the stored naive
clock; labelling hour *ends* does not verify the physical acquisition timezone.
No weights, environmental gaps or feeding amounts are interpolated.
"""
import json,gzip,hashlib
from datetime import datetime,timezone
from pathlib import Path
from sqlalchemy import text
from backend.app.core.database import engine
from backend.app.core.config import get_settings

def export(destination):
    schema=get_settings().legacy_database_name
    assert schema and schema.replace('_','').isalnum()
    with engine.connect().execution_options(isolation_level='REPEATABLE READ') as c:
        with c.begin():
            raw=c.execute(text(f'''SELECT b.id,b.fecha_muestreo,b.prom_peso_g,b.cantidad_muestreo,
              b.total_alimento_consumido_kg,b.cantidad_peces_actuales,b.updated_at,
              ce.campania_especie_id,ce.piscina_id,COUNT(d.id) sample_n,
              AVG(d.peso_g) sample_mean_g,STDDEV_SAMP(d.peso_g) sample_sd_g
              FROM {schema}.biometrias b JOIN {schema}.campania_etapas ce ON ce.id=b.campania_etapa_id
              LEFT JOIN {schema}.biometria_detalles d ON d.biometria_id=b.id
              WHERE b.deleted_at IS NULL AND ce.deleted_at IS NULL AND ce.piscina_id=1
              AND ce.campania_especie_id=2
              GROUP BY b.id,ce.campania_especie_id,ce.piscina_id ORDER BY b.fecha_muestreo''')).mappings().all()
            assert raw and all(r['sample_n']>=2 for r in raw)
            bios=[]
            for r in raw:
                d=dict(r)
                for k in ['prom_peso_g','total_alimento_consumido_kg','sample_mean_g','sample_sd_g']:
                    d[k]=float(d[k]) if d[k] is not None else None
                assert abs(d['sample_mean_g']-d['prom_peso_g'])<1e-5,'Biometry summary differs from detail'
                bios.append(d)
            start=str(bios[0]['fecha_muestreo'])+' 00:00:00'
            # Seven observed days before the first weight initialize environmental context.
            clauses="piscina_id=1 AND fecha_medicion>=DATE_SUB(:start,INTERVAL 7 DAY)"
            hour="DATE_FORMAT(DATE_ADD(fecha_medicion,INTERVAL 1 HOUR),'%Y-%m-%d %H:00:00')"
            water=c.execute(text(f'''SELECT {hour} AS hour_end,AVG(temperatura),AVG(oxigeno_disuelto),
              AVG(ph),COUNT(*),MAX(created_at) FROM {schema}.parametro_aguas
              WHERE {clauses} AND deleted_at IS NULL GROUP BY hour_end ORDER BY hour_end'''),{'start':start}).all()
            light=c.execute(text(f'''SELECT {hour} AS hour_end,AVG(iluminancia),COUNT(*),MAX(created_at)
              FROM {schema}.parametro_ambientes WHERE {clauses} GROUP BY hour_end ORDER BY hour_end'''),{'start':start}).all()
            details=c.execute(text(f'''SELECT d.biometria_id,d.numero,d.peso_g,d.longitud_cm FROM
              {schema}.biometria_detalles d JOIN {schema}.biometrias b ON b.id=d.biometria_id
              JOIN {schema}.campania_etapas ce ON ce.id=b.campania_etapa_id
              WHERE b.deleted_at IS NULL AND ce.deleted_at IS NULL AND ce.piscina_id=1
              AND ce.campania_especie_id=2 ORDER BY b.fecha_muestreo,d.numero,d.id''')).all()
            counts={t:int(c.execute(text(f'SELECT COUNT(*) FROM {schema}.{t}')).scalar_one()) for t in
                ['alimentacion_tablas','alimentacion_semanas','parametro_aguas','parametro_ambientes']}
    def rows(rr):
        return [[str(v) if isinstance(v,datetime) else float(v) if hasattr(v,'as_tuple') else v for v in r] for r in rr]
    data={'captured_at':datetime.now(timezone.utc).isoformat(),'schema':schema,'pond_id':1,'cohort_id':2,
      'physical_clock_alignment_verified':False,'transaction_isolation':'REPEATABLE READ',
      'aggregation':'floor(stored_measurement_time/hour)+1h: complete-hour end, unlike earlier floor-labelled snapshots',
      'biometries':bios,'detail_columns':['biometry_id','number','weight_g','length_cm'],
      'details':rows(details),'table_counts_unfiltered':counts,
      'water_hour_columns':['hour_end','temperature_c','oxygen_mg_l','ph','n','last_received'],
      'light_hour_columns':['hour_end','light_lux','n','last_received'],
      'water_hourly':rows(water),'light_hourly':rows(light),
      'feeding_note':'Existing alimentation tables/weekly computed schedules are not verified actual delivered feed; excluded.'}
    b=gzip.compress(json.dumps(data,default=str,allow_nan=False).encode(),mtime=0)
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    destination.write_bytes(b);destination.chmod(0o600)
    print(json.dumps({'path':str(destination),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b),
      'biometries':len(bios),'weight_records':len(details),'water_hour_bins':len(water),'light_hour_bins':len(light)}))

if __name__=='__main__':
    import sys
    export(sys.argv[1])
