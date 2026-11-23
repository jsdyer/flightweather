import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from refresh import config,validate,merge,key
class RefreshTests(unittest.TestCase):
 def setUp(self): self.cfg={'airports':[{'icao':'CYVR','label':'Vancouver'}],'historyDays':90,'observationHours':24,'requestDelaySeconds':1}
 def test_config_expands_without_count_assumptions(self):
  self.cfg['airports'].append({'icao':'CYYZ','label':'Toronto'});self.assertEqual(len(config(self.cfg)['airports']),2)
 def test_duplicate_airports_rejected(self):
  self.cfg['airports']*=2
  with self.assertRaises(ValueError):config(self.cfg)
 def test_malformed_or_truncated_response_rejected(self):
  with self.assertRaises(ValueError):validate({},'metar',['CYVR'])
  with self.assertRaises(ValueError):validate([{}]*400,'metar',['CYVR'])
  with self.assertRaises(ValueError):validate([{'icaoId':'CYHZ','obsTime':1,'rawOb':'test'}],'metar',['CYVR'])
 def test_repeat_capture_preserves_first_seen_and_raw_corrections(self):
  row={'icaoId':'CYVR','obsTime':1795430000,'rawOb':'A','wspd':0}
  a=merge({},[row],[],self.cfg,'2026-11-23T10:00:00Z',[])
  b=merge(a,[{**row,'receiptTime':'new'}],[],self.cfg,'2026-11-23T11:00:00Z',[])
  self.assertEqual(len(b['observations']),1);self.assertEqual(b['observations'][0]['firstCapturedAt'],a['retrievedAt'])
  c=merge(b,[{**row,'rawOb':'B','wspd':4}],[],self.cfg,'2026-11-23T12:00:00Z',[])
  self.assertEqual(len(c['observations']),2)
 def test_removed_airport_retained_in_earlier_history(self):
  old={'schema':'coolcode.flightweather.v1','airports':[{'icao':'CYHZ','label':'Halifax'}],'observations':[],'forecasts':[],'captures':[]}
  out=merge(old,[],[],self.cfg,'2026-11-23T10:00:00Z',[])
  self.assertEqual(len(out['airports']),2)
if __name__=='__main__':unittest.main()
