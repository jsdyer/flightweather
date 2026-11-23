export const seconds=v=>typeof v==='number'?v:Date.parse(v)/1000;
export const number=v=>typeof v==='number'&&Number.isFinite(v)?v:null;
export function visibility(v){if(number(v)!==null)return {value:v,bound:'exact'};if(typeof v==='string'&&/^\d+(\.\d+)?\+$/.test(v))return {value:parseFloat(v),bound:'greater'};return null;}
export function ceiling(row){if(number(row.vertVis)!==null)return {value:row.vertVis,type:'vertical visibility'};const clouds=Array.isArray(row.clouds)?row.clouds:[];const layers=clouds.filter(x=>['BKN','OVC'].includes(x.cover)&&number(x.base)!==null);if(layers.length)return {value:Math.min(...layers.map(x=>x.base)),type:'ceiling'};return {value:null,type:clouds.length&&clouds.every(x=>['FEW','SCT','CLR','SKC','NSC'].includes(x.cover))?'no ceiling reported':'unknown'};}
export function directionDifference(a,b){if(number(a)===null||number(b)===null)return null;return Math.min(Math.abs(a-b)%360,360-Math.abs(a-b)%360);}
export function groupsAt(forecast,time){const t=seconds(time);const groups=forecast.fcsts||[];const base=groups.filter(g=>(!g.fcstChange||g.fcstChange==='FM')&&g.timeFrom<=t&&t<g.timeTo).sort((a,b)=>b.timeFrom-a.timeFrom)[0];const conditional=groups.filter(g=>g.fcstChange&&g.fcstChange!=='FM'&&g.timeFrom<=t&&t<g.timeTo);
 const changing=base&&groups.some(g=>g.fcstChange==='BECMG'&&g.timeFrom>=base.timeFrom&&g.timeFrom<=t);
 return {base:changing?null:base||null,conditional,reason:changing?'BECMG transition or changed conditions: no deterministic pairing.':base?null:'No prevailing period at this time.'};}
export function available(data,at){const end=seconds(at);return {...data,observations:data.observations.filter(r=>seconds(r.firstCapturedAt)<=end),forecasts:data.forecasts.filter(r=>seconds(r.firstCapturedAt)<=end)};}
export function compare(forecast,observations,mode='prospective'){
 const issue=seconds(forecast.issueTime),captured=seconds(forecast.firstCapturedAt);
 return observations.filter(o=>o.icaoId===forecast.icaoId&&o.obsTime>=forecast.validTimeFrom&&o.obsTime<forecast.validTimeTo&&o.obsTime>=issue&&(mode!=='prospective'||o.obsTime>captured)).sort((a,b)=>a.obsTime-b.obsTime).map(o=>{
  const group=groupsAt(forecast,o.obsTime),f=group.base;
  return {observation:o,forecast:f,conditional:group.conditional,reason:group.reason,prospective:o.obsTime>captured,leadHours:(o.obsTime-issue)/3600,
   windDifference:f&&number(f.wspd)!==null&&number(o.wspd)!==null?o.wspd-f.wspd:null,
   directionDifference:f&&f.wspd>0&&o.wspd>0?directionDifference(f.wdir,o.wdir):null,
   ceilingDifference:f&&ceiling(f).value!==null&&ceiling(o).value!==null?ceiling(o).value-ceiling(f).value:null};
 });
}
export function airportRecords(data,icao){return {observations:data.observations.filter(x=>x.icaoId===icao).sort((a,b)=>b.obsTime-a.obsTime),forecasts:data.forecasts.filter(x=>x.icaoId===icao).sort((a,b)=>seconds(b.issueTime)-seconds(a.issueTime))};}
export function validateLedger(data){
 const validTime=v=>Number.isFinite(seconds(v))&&Math.abs(seconds(v))<8640000000000;
 const id=v=>typeof v==='string'&&/^[a-f0-9]{20}$/.test(v);
 const airport=v=>typeof v==='string'&&/^[A-Z]{4}$/.test(v);
 const interval=(a,b)=>number(a)!==null&&number(b)!==null&&validTime(a)&&validTime(b)&&a<b;
 const clouds=r=>r.clouds===undefined||(Array.isArray(r.clouds)&&r.clouds.every(c=>c&&typeof c.cover==='string'&&(c.base==null||number(c.base)!==null)));
 if(data?.schema!=='coolcode.flightweather.v1'||!Array.isArray(data.airports)||!Array.isArray(data.observations)||!Array.isArray(data.forecasts)||!Array.isArray(data.captures)||!validTime(data.retrievedAt))throw Error('Not a Flight Weather receipt.');
 if(!data.airports.length||data.airports.length>200||data.observations.length>300000||data.forecasts.length>30000||!data.captures.length||data.captures.length>12000)throw Error('Receipt is empty or too large.');
 const ids=new Set();for(const a of data.airports){if(!airport(a.icao)||typeof a.label!=='string'||!a.label.trim()||(a.region!==undefined&&typeof a.region!=='string')||ids.has(a.icao))throw Error('Invalid airport.');ids.add(a.icao);}
 for(const c of data.captures)if(!validTime(c.at)||!Array.isArray(c.airports)||!c.airports.every(v=>airport(v)&&ids.has(v))||(c.coverage!==undefined&&(!Array.isArray(c.coverage)||!c.coverage.every(r=>r&&ids.has(r.icao)&&number(r.metars)!==null&&r.metars>=0&&number(r.tafs)!==null&&r.tafs>=0))))throw Error('Invalid capture.');
 for(const o of data.observations)if(!ids.has(o.icaoId)||!id(o.id)||number(o.obsTime)===null||!validTime(o.obsTime)||typeof o.rawOb!=='string'||!validTime(o.firstCapturedAt)||!validTime(o.lastCapturedAt)||seconds(o.firstCapturedAt)>seconds(o.lastCapturedAt)||!clouds(o))throw Error('Invalid observation.');
 for(const f of data.forecasts){if(!ids.has(f.icaoId)||!id(f.id)||!Array.isArray(f.fcsts)||!f.fcsts.length||f.fcsts.length>200||typeof f.rawTAF!=='string'||!validTime(f.issueTime)||!validTime(f.firstCapturedAt)||!validTime(f.lastCapturedAt)||seconds(f.firstCapturedAt)>seconds(f.lastCapturedAt)||!interval(f.validTimeFrom,f.validTimeTo))throw Error('Invalid forecast.');
  for(const g of f.fcsts)if(!g||!interval(g.timeFrom,g.timeTo)||g.timeFrom<f.validTimeFrom||g.timeTo>f.validTimeTo||!clouds(g)||(g.fcstChange!=null&&typeof g.fcstChange!=='string'))throw Error('Invalid forecast period.');
 }
 return data;
}
export function csv(rows){const quote=v=>'"'+String(v??'').replaceAll('"','""')+'"';return rows.map(r=>r.map(v=>quote(typeof v==='string'&&/^[=+@\-\t\r]/.test(v)?"'"+v:v)).join(',')).join('\r\n');}
