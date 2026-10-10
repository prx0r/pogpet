#!/usr/bin/env python3
"""Scaffold a new pack from _template.  python3 tools/new_pack.py <SKU> "<name>" <family> <personalised|fixed> <supplier> <process>"""
import sys, os, json, shutil
CAT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sku, name, fam, kind, sup, proc = sys.argv[1:7]; dst = f'{CAT}/packs/{sku}'
if os.path.exists(dst): sys.exit(f'{sku} exists')
shutil.copytree(f'{CAT}/_template', dst)
P = json.load(open(f'{dst}/product.json')); P.update(sku=sku, name=name, family=fam, kind=kind)
P['manufacture'].update(supplier=sup, process=proc); P['manufacture']['print_file']['format'] = json.load(open(f'{CAT}/config.json'))['processes'][proc]['print_format']
json.dump(P, open(f'{dst}/product.json', 'w'), indent=1); print('created', dst)
