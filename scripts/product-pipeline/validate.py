"""python3 validate.py products/*.json  -> schema check every product spec."""
import sys, json
from jsonschema import Draft202012Validator
S = json.load(open(__file__.rsplit('/', 1)[0] + '/schema/product.schema.json')); bad = 0
for p in sys.argv[1:]:
    errs = list(Draft202012Validator(S).iter_errors(json.load(open(p))))
    print(('OK  ' if not errs else 'FAIL'), p, *[f'\n   {"/".join(map(str, e.path))}: {e.message}' for e in errs]); bad += bool(errs)
sys.exit(bad)
