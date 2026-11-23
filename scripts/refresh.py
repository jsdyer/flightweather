#!/usr/bin/env python3
"""Retain AWC reports. A failed fetch/validation leaves the ledger untouched."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import hashlib, json, re, time
from urllib.request import Request, urlopen
from urllib.parse import urlencode
ROOT = Path(__file__).resolve().parents[1]
API = 'https://aviationweather.gov/api/data/'
UA = 'CoolCode-FlightWeather/1.0 (https://coolcode.ca/flightweather/)'

def stamp(): return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
def epoch(s): return datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()
def config(data):
    airports=data.get('airports')
    if not isinstance(airports,list) or not 1<=len(airports)<=min(int(data.get('maxAirports',40)),40): raise ValueError('Configure 1–40 airports.')
    ids=[]
    for a in airports:
        if not isinstance(a,dict) or not re.fullmatch('[A-Z]{4}',a.get('icao','')) or not isinstance(a.get('label'),str) or not a['label'].strip(): raise ValueError('Every airport needs a four-letter ICAO code and label.')
        ids.append(a['icao'])
    if len(set(ids))!=len(ids): raise ValueError('Duplicate ICAO code.')
    if not 2<=int(data.get('historyDays',90))<=365: raise ValueError('historyDays must be 2–365.')
    if not 1<=int(data.get('observationHours',24))<=48: raise ValueError('observationHours must be 1–48.')
    if not 1<=float(data.get('requestDelaySeconds',1))<=30: raise ValueError('Delay must be 1–30 seconds.')
    return data

def fetch(kind,ids,hours=None):
    params={'ids':','.join(ids),'format':'json'}
    if hours is not None: params['hours']=hours
    url=API+kind+'?'+urlencode(params)
    with urlopen(Request(url,headers={'User-Agent':UA,'Accept':'application/json'}),timeout=45) as response:
        if response.status==204: return [],url
        raw=response.read(8_000_001)
        if len(raw)>8_000_000: raise ValueError('Response exceeded 8 MB.')
        rows=json.loads(raw)
    validate(rows,kind,ids)
    return rows,url

def validate(rows,kind,ids):
    if not isinstance(rows,list) or len(rows)>=400: raise ValueError('Unexpected or potentially truncated API response.')
    for row in rows:
        if not isinstance(row,dict) or row.get('icaoId') not in ids: raise ValueError('Unexpected airport in API response.')
        if kind=='metar':
            if not isinstance(row.get('obsTime'),(int,float)) or not row.get('rawOb'): raise ValueError('Observation missing time or raw report.')
        else:
            if not row.get('issueTime') or not row.get('rawTAF') or not isinstance(row.get('fcsts'),list) or not row['fcsts']: raise ValueError('Forecast missing issue time, periods or raw report.')
            epoch(row['issueTime'])
            if not isinstance(row.get('validTimeFrom'),(int,float)) or not isinstance(row.get('validTimeTo'),(int,float)) or row['validTimeFrom']>=row['validTimeTo']: raise ValueError('Invalid forecast validity.')
            for group in row['fcsts']:
                if not isinstance(group.get('timeFrom'),(int,float)) or not isinstance(group.get('timeTo'),(int,float)) or group['timeFrom']>=group['timeTo']: raise ValueError('Invalid forecast group.')

def key(row,kind):
    # Include all meteorological data, not changing ingestion flags/timestamps.
    stable={k:v for k,v in row.items() if k not in ('receiptTime','dbPopTime','mostRecent','prior','firstCapturedAt','lastCapturedAt','id')}
    return hashlib.sha256(json.dumps(stable,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:20]

def merge(old,observations,forecasts,cfg,now,requests):
    if old and old.get('schema')!='coolcode.flightweather.v1': raise ValueError('Unknown existing ledger schema.')
    cutoff=epoch(now)-cfg['historyDays']*86400
    out={'schema':'coolcode.flightweather.v1','retrievedAt':now,'source':'NOAA/NWS Aviation Weather Center','airports':old.get('airports',[]).copy(),'captures':old.get('captures',[]).copy()}
    airports={a['icao']:a for a in out['airports']}
    airports.update({a['icao']:a for a in cfg['airports']});out['airports']=list(airports.values())
    for name,rows,kind,field in [('observations',observations,'metar','obsTime'),('forecasts',forecasts,'taf','validTimeTo')]:
        entries={r['id']:r.copy() for r in old.get(name,[]) if r.get(field,0)>=cutoff}
        for r in rows:
            ident=key(r,kind)
            if ident in entries: entries[ident]['lastCapturedAt']=now
            else: entries[ident]={**r,'id':ident,'firstCapturedAt':now,'lastCapturedAt':now}
        out[name]=sorted(entries.values(),key=lambda r:(r['icaoId'],r[field],r['id']))
    out['captures']=[c for c in out['captures'] if epoch(c['at'])>=cutoff]
    out['captures'].append({'at':now,'airports':[a['icao'] for a in cfg['airports']],'metars':len(observations),'tafs':len(forecasts),'requests':requests,'coverage':[{'icao':a['icao'],'metars':sum(r['icaoId']==a['icao'] for r in observations),'tafs':sum(r['icaoId']==a['icao'] for r in forecasts)} for a in cfg['airports']]})
    return out

def main():
    cfg=config(json.loads((ROOT/'web/config.json').read_text()))
    rows=[];forecasts=[];requests=[]
    for airport in cfg['airports']:
        got,url=fetch('metar',[airport['icao']],cfg['observationHours']);rows.extend(got);requests.append(url)
        time.sleep(cfg['requestDelaySeconds'])
        got,url=fetch('taf',[airport['icao']]);forecasts.extend(got);requests.append(url)
        time.sleep(cfg['requestDelaySeconds'])
    if not rows: raise ValueError('No observations returned for any configured airport; preserving last capture.')
    path=ROOT/'web/data/ledger.json';path.parent.mkdir(parents=True,exist_ok=True)
    old=json.loads(path.read_text()) if path.exists() else {}
    data=merge(old,rows,forecasts,cfg,stamp(),requests)
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n');tmp.replace(path)
    print(f"Retained {len(data['observations'])} METAR/SPECI reports and {len(data['forecasts'])} TAF editions across {len(data['airports'])} airports. Captured {data['retrievedAt']}.")
if __name__=='__main__': main()
