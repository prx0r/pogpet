#!/usr/bin/env python3
"""Part card → Wokwi custom chip (chip.json + chip.c, Chips API, compiles to WASM with wokwi-cli).
This is fidelity level 2: the REAL ESP32 firmware (ESP-IDF/Arduino) talks I2C to a chip generated from the same card the
Python twin uses. Running it needs wokwi-cli and a WOKWI_CLI_TOKEN (not available in this sandbox, so generated only).
  python3 wokwi/gen_chip.py cards/bh1750.card.json out/wokwi/"""
import json, os, sys
c = json.load(open(sys.argv[1])); out = sys.argv[2]; os.makedirs(out, exist_ok=True)
assert c['model'] == 'i2c_command_device', 'only i2c_command_device cards so far'
DS = c.get("datasheet", {}).get("url", ""); addr = int(c['interface']['addresses']['ADDR_L'], 16); H = c['modes']['H']
json.dump({'name': c['mpn'], 'author': 'oddhobb hwsim (generated from part card)', 'pins': ['VCC', 'GND', 'SCL', 'SDA', 'ADDR', 'DVI'],
           'controls': [{'id': 'lux', 'label': 'Illuminance (lx)', 'type': 'range', 'min': 0, 'max': 65535, 'step': 1}]},
          open(f'{out}/{c["id"]}.chip.json', 'w'), indent=1)
cases = []
for o in c['opcodes']:
    m, v = int(o['mask'], 16), int(o['value'], 16)
    body = []
    if 'goto' in o: body.append(f'chip->state = ST_{o["goto"].upper()};')
    if 'mode' in o: body.append(f'chip->mode = MODE_{o["mode"]}; chip->t_start = get_sim_nanos();')
    if o.get('effect') == 'data=0': body.append('if (chip->state != ST_POWER_DOWN) chip->data = 0;')
    if o.get('effect', '').startswith('mtreg[7:5]'): body.append('chip->mtreg = (chip->mtreg & 0x1F) | ((op & 7) << 5);')
    if o.get('effect', '').startswith('mtreg[4:0]'): body.append('chip->mtreg = (chip->mtreg & 0xE0) | (op & 0x1F);')
    cases.append(f'  if ((op & 0x{m:02X}) == 0x{v:02X}) {{ /* {o["name"]} */ {" ".join(body)} return true; }}')
states = ''.join(f'  ST_{s.upper()},\n' for s in c['states'])
src = f'''// GENERATED from part card {c["id"]} ({c["mpn"]}) — do not edit; edit the card and regenerate.
// Datasheet: {DS}
#include "wokwi-api.h"
#include <stdint.h>
void *calloc(unsigned long n, unsigned long size);  /* from libc; avoids host timer_t clash */
typedef enum {{
{states}}} state_t;
typedef enum {{ MODE_H, MODE_H2, MODE_L }} mode_t_;
typedef struct {{ state_t state; mode_t_ mode; uint16_t data; uint8_t mtreg; uint64_t t_start; uint32_t lux_attr; uint8_t rd; }} chip_t;

static double conv_ms(chip_t *chip) {{
  double t = chip->mode == MODE_L ? {c["modes"]["L"]["t_typ_ms"]} : {H["t_typ_ms"]};
  return t * chip->mtreg / 69.0;
}}
static void update(chip_t *chip) {{
  if (chip->state != ST_MEASURING_CONT && chip->state != ST_MEASURING_ONCE) return;
  if ((get_sim_nanos() - chip->t_start) / 1e6 < conv_ms(chip)) return;
  double lux = attr_read_float(chip->lux_attr);
  double lpc = (chip->mode == MODE_L ? 4.0 : 1.0) / 1.2 * (69.0 / chip->mtreg) / (chip->mode == MODE_H2 ? 2.0 : 1.0);
  double counts = lux * {c["measurement"]["accuracy_ratio"]["typ"]} / (1.2 * lpc);
  chip->data = counts > 65535 ? 65535 : (uint16_t)counts;
  chip->t_start = get_sim_nanos();
  if (chip->state == ST_MEASURING_ONCE) chip->state = ST_POWER_DOWN;
}}
static bool on_write(void *ud, uint8_t op) {{
  chip_t *chip = ud;
{chr(10).join(cases)}
  return false; // undefined opcode → NACK
}}
static uint8_t on_read(void *ud) {{ chip_t *chip = ud; update(chip); return (chip->rd++ & 1) ? (chip->data & 0xFF) : (chip->data >> 8); }}
static bool on_connect(void *ud, uint32_t address, bool read) {{ chip_t *chip = ud; update(chip); chip->rd = 0; return true; }}
static void on_disconnect(void *ud) {{}}

void chip_init(void) {{
  chip_t *chip = calloc(1, sizeof(chip_t));
  chip->state = ST_{c["initial_state"].upper()}; chip->mtreg = {c["registers"]["mtreg"]["reset"]};
  chip->lux_attr = attr_init_float("lux", 300.0);
  const i2c_config_t cfg = {{ .user_data = chip, .address = 0x{addr:02X}, .scl = pin_init("SCL", INPUT), .sda = pin_init("SDA", INPUT),
    .connect = on_connect, .read = on_read, .write = on_write, .disconnect = on_disconnect }};
  i2c_init(&cfg);
}}
'''
open(f'{out}/{c["id"]}.chip.c', 'w').write(src); print('wrote', out)
