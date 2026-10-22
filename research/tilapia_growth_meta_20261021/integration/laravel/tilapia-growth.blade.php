<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Crecimiento ML · Sismapiscis</title>
<style>
:root{font-family:system-ui,sans-serif;color:#16312f;background:#f3f7f6}*{box-sizing:border-box}body{margin:0}main{max-width:1120px;margin:auto;padding:32px 20px}a{color:#126b5b}header{display:flex;justify-content:space-between;gap:20px;align-items:center}h1{font-size:32px;margin:18px 0 8px}h2{font-size:19px;margin:0 0 14px}.muted{color:#526861}.pill{background:#fff1cc;color:#76530b;padding:7px 12px;border-radius:20px;font-size:13px}.card{background:white;border:1px solid #dce6e1;border-radius:16px;padding:24px;margin:20px 0}.controls{display:flex;gap:12px;align-items:center;flex-wrap:wrap}input,button{font:inherit;padding:10px 14px;border:1px solid #b4c9c0;border-radius:8px}input{width:85px}button{background:#126b5b;color:white;cursor:pointer}button:disabled{opacity:.6}#error{color:#9d3026}svg{width:100%;height:auto;min-height:200px}table{border-collapse:collapse;width:100%}td,th{padding:12px 8px;border-bottom:1px solid #e1e9e5;text-align:left}th{font-size:13px;color:#526861}#metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:15px}.metric{border-left:3px solid #126b5b;padding-left:14px}.metric strong{display:block;font-size:27px;margin:6px 0}.legend{display:flex;gap:25px;flex-wrap:wrap;font-size:14px}.observed{color:#126b5b}.projected{color:#7f56be}.scroll{overflow:auto}code{font-size:11px;overflow-wrap:anywhere}p{line-height:1.6}.hidden{display:none}@media(max-width:600px){h1{font-size:26px}#metrics{grid-template-columns:1fr}header{align-items:flex-start}.card{padding:16px}}
</style>
</head>
<body><main>
<header><a href="{{ route('monitoreo.modelosmls.index', [], false) }}">← Modelos de aprendizaje automático</a><span class="pill">Experimental · v0.3</span></header>
<h1>Crecimiento de tilapia con ML</h1>
<p class="muted">ExtraTrees entrenado con secuencias de peso. Proyecciones del peso medio del lote, pendientes de validación con nuevas biometrías.</p>
<form id="form" class="controls"><label for="pond">Piscina</label><input id="pond" name="piscina_id" type="number" min="1" value="{{ $pond }}" required><button id="refresh">Actualizar proyección</button><span id="state" role="status" aria-live="polite"></span></form>
<p id="error" role="alert"></p>
<div id="content" class="hidden">
<section class="card" id="metrics"></section>
<section class="card"><h2>Peso observado y proyección</h2><div class="legend"><span class="observed">● Peso observado</span><span class="projected">┄ Proyección ML</span></div><svg id="chart" viewBox="0 0 960 360" role="img" aria-label="Peso medio observado y proyecciones de peso medio en gramos"></svg><p class="muted">La línea discontinua representa una proyección, no un peso medido. No se dispone de un intervalo de predicción calibrado.</p><div class="scroll"><table><thead><tr><th>Horizonte desde hoy</th><th>Fecha objetivo (Lima)</th><th>Peso proyectado</th><th>Desde última biometría</th></tr></thead><tbody id="forecasts"></tbody></table></div></section>
<section class="card"><h2>Biometrías usadas por el modelo</h2><div class="scroll"><table><thead><tr><th>Fecha de muestreo</th><th>Peso medio</th><th>Peces muestreados</th></tr></thead><tbody id="bios"></tbody></table></div><p class="muted">Las muestras pertenecen al mismo lote. La base registra el día de muestreo, sin hora; el cálculo toma el inicio de ese día en Lima.</p></section>
<section class="card"><h2>Sensores y luz</h2><p id="sensors"></p><p id="light"></p><p class="muted">Las fechas de medición y de recepción requieren verificar los relojes. El contador de oscuridad no permite reconstruir un fotoperiodo fiable. El registro horario conserva los pronósticos o el motivo de bloqueo para evaluarlos frente a futuras biometrías.</p></section>
<section class="card hidden" id="interval-context"><h2>Sensores y alimento: prueba por intervalos</h2><p id="interval-result"></p><div class="scroll"><table><thead><tr><th>Entradas del modelo</th><th>Error medio absoluto</th></tr></thead><tbody id="interval-metrics"></tbody></table></div><p id="interval-scope" class="muted"></p><p class="muted">Cada versión usa un único proceso gaussiano y pesos medidos. El alimento corresponde a totales ingresados, cuya entrega real está pendiente de verificar. Esta prueba retrospectiva no activa un nuevo predictor ni demuestra precisión en futuras biometrías. La luz no se incluyó por falta de cobertura comparable.</p></section>
<section class="card"><h2>Alcance de la evidencia</h2><p>En cuatro fechas locales ya conocidas, el error absoluto medio retrospectivo fue <strong>12,76 g</strong>, frente a <strong>17,10 g</strong> con tendencia reciente. Este resultado es de desarrollo: no demuestra el error que tendrá una nueva campaña.</p><p class="muted">A 28 días desde hoy, el tiempo total desde la última biometría puede superar los 28 días estudiados en las referencias externas. No se ofrece una certeza cercana a 1 ni una garantía de crecimiento.</p><p id="trace" class="muted"></p></section>
</div>
<script>
const endpoint = {{ Illuminate\Support\Js::from(route('monitoreo.crecimientoml.data', [], false)) }};
const $ = id => document.getElementById(id);
const n = (v,d=2) => Number(v).toLocaleString('es-PE',{maximumFractionDigits:d});
const date = t => new Date(t).toLocaleDateString('es-PE',{timeZone:'America/Lima',day:'2-digit',month:'short',year:'numeric'});
function cell(row,text){const c=document.createElement('td');c.textContent=text;row.append(c)}
function table(id,rows){$(id).replaceChildren();rows.forEach(values=>{const r=document.createElement('tr');values.forEach(v=>cell(r,v));$(id).append(r)})}
function chart(bios,forecasts){
 const svg=$('chart');svg.replaceChildren();const ns='http://www.w3.org/2000/svg';
 function el(tag,attrs,text){const e=document.createElementNS(ns,tag);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,v));if(text!==undefined)e.textContent=text;svg.append(e);return e}
 const obs=bios.map(b=>({x:Date.parse(b.observed_at),y:b.mean_weight_g}));
 const pred=[obs.at(-1),...forecasts.map(f=>({x:Date.parse(f.target_at),y:f.predicted_mean_weight_g}))];
 const all=[...obs,...pred],xmin=Math.min(...all.map(p=>p.x)),xmax=Math.max(...all.map(p=>p.x));
 const ymin=Math.max(0,Math.floor(Math.min(...all.map(p=>p.y))/10)*10-10),ymax=Math.ceil(Math.max(...all.map(p=>p.y))/10)*10+10;
 const X=x=>70+840*(x-xmin)/(xmax-xmin||1),Y=y=>295-245*(y-ymin)/(ymax-ymin||1);
 for(let i=0;i<=5;i++){const y=ymin+(ymax-ymin)*i/5;el('line',{x1:70,x2:910,y1:Y(y),y2:Y(y),stroke:'#e3ebe7'});el('text',{x:60,y:Y(y)+5,'text-anchor':'end',fill:'#526861','font-size':14},n(y,0))}
 el('text',{x:70,y:25,fill:'#526861','font-size':14},'Peso medio (g)');
 [obs[0],obs.at(-1),pred.at(-1)].forEach(p=>el('text',{x:X(p.x),y:325,'text-anchor':'middle',fill:'#526861','font-size':13},date(p.x)));
 [[obs,'#126b5b',null],[pred,'#7f56be','8 6']].forEach(([pts,color,dash])=>{const attrs={points:pts.map(p=>`${X(p.x)},${Y(p.y)}`).join(' '),fill:'none',stroke:color,'stroke-width':3};if(dash)attrs['stroke-dasharray']=dash;el('polyline',attrs);pts.forEach(p=>{const c=el('circle',{cx:X(p.x),cy:Y(p.y),r:5,fill:color});const title=document.createElementNS(ns,'title');title.textContent=`${date(p.x)}: ${n(p.y)} g`;c.append(title)})});
}
async function load(e){
 if(e)e.preventDefault();if(!$('form').reportValidity())return;
 $('refresh').disabled=true;$('state').textContent='Consultando el modelo…';$('error').textContent='';$('content').classList.add('hidden');
 try{
  const r=await fetch(endpoint+'?piscina_id='+encodeURIComponent($('pond').value),{headers:{Accept:'application/json'},cache:'no-store'});
  const data=await r.json();if(!r.ok)throw new Error(data.message||'No se pudo consultar el modelo.');
  const fs=data.forecasts,first=fs[0],ctx=first.source_context,bios=ctx.biometries;
  $('metrics').replaceChildren();[['Último peso observado',n(first.anchor_observed_weight_g)+' g',date(first.anchor_observed_at)],['Proyección a 7 días',n(first.predicted_mean_weight_g)+' g',date(first.target_at)],['Edad de la última muestra',n(first.anchor_age_days,1)+' días','No es una medición de hoy']].forEach(([label,value,detail])=>{const d=document.createElement('div');d.className='metric';const l=document.createElement('span'),v=document.createElement('strong'),s=document.createElement('span');l.textContent=label;v.textContent=value;s.textContent=detail;d.append(l,v,s);$('metrics').append(d)});
  table('forecasts',fs.map(f=>[f.projection_days+' días',date(f.target_at),n(f.predicted_mean_weight_g)+' g',n(f.duration_from_observed_anchor_days,1)+' días']));
  table('bios',bios.map((b,i)=>[date(b.observed_at),n(b.mean_weight_g)+' g',ctx.sample_sizes[i]]));chart(bios,fs);
  $('sensors').textContent=first.sensor_features_used.length?'Variables de sensores usadas: '+first.sensor_features_used.join(', '):'Variables de sensores usadas para predecir el peso: ninguna. El efecto de temperatura, oxígeno, pH y luz todavía no está aprendido.';
  const li=ctx.light_inventory;$('light').textContent=`Luz: ${n(li.n,0)} registros; rango ${n(li.minimum_lux,0)}–${n(li.maximum_lux,0)} lux. Última fecha registrada: ${li.last_record||'sin datos'} (zona de esa columna pendiente de verificar).`;
  $('trace').textContent=`Emitido: ${new Date(first.issued_at).toLocaleString('es-PE',{timeZone:'America/Lima'})} (Lima). Modelo: ${first.model_version}. Huella: ${first.artifact_sha256}.`;
  $('interval-context').classList.add('hidden');
  const ic=data.interval_context;
  if(ic&&ic.development_metrics){
   const m=ic.development_metrics,v=m.variants;
   table('interval-metrics',[
    ['Peso inicial y tiempo',n(v.weight_time.MAE_g)+' g'],
    ['Peso inicial, tiempo y agua',n(v.weight_time_water.MAE_g)+' g'],
    ['Peso inicial, tiempo y alimento ingresado',n(v.weight_time_feed.MAE_g)+' g'],
    ['Peso inicial, tiempo, alimento ingresado y agua',n(v.weight_time_feed_water.MAE_g)+' g'],
    ['Referencia: conservar último peso medido',n(m.persistence_g.MAE_g)+' g']]);
   $('interval-result').textContent=v.weight_time_feed_water.MAE_g<m.persistence_g.MAE_g?'El candidato reduce el error frente a conservar el último peso en estas fechas de desarrollo; falta validación independiente.':'El candidato con agua y alimento no mejora la referencia de conservar el último peso. Continúa como experimento.';
   $('interval-scope').textContent=`Comparación sobre las mismas ${m.n_dates} fechas: ${m.dates.map(t=>t.slice(0,10)).join(', ')}. Intervalos excluidos por cobertura de agua: ${m.excluded_dates.map(t=>t.slice(0,10)).join(', ')||'ninguno'}. Menor error es mejor. Las fechas conservan el reloj registrado, pendiente de verificar.`;
   $('interval-context').classList.remove('hidden');
  }
  $('content').classList.remove('hidden');$('state').textContent='Proyección actualizada';
 }catch(err){$('error').textContent=err.message;$('state').textContent='Sin proyección disponible'}finally{$('refresh').disabled=false}
}
$('form').addEventListener('submit',load);load();
</script></main></body></html>
