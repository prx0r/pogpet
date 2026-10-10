// GENERATED from part card bh1750 (BH1750FVI-TR) — do not edit; edit the card and regenerate.
// Datasheet: https://www.mouser.com/datasheet/2/348/bh1750fvi-e-186247.pdf
#include "wokwi-api.h"
#include <stdint.h>
void *calloc(unsigned long n, unsigned long size);  /* from libc; avoids host timer_t clash */
typedef enum {
  ST_POWER_DOWN,
  ST_POWER_ON,
  ST_MEASURING_CONT,
  ST_MEASURING_ONCE,
} state_t;
typedef enum { MODE_H, MODE_H2, MODE_L } mode_t_;
typedef struct { state_t state; mode_t_ mode; uint16_t data; uint8_t mtreg; uint64_t t_start; uint32_t lux_attr; uint8_t rd; } chip_t;

static double conv_ms(chip_t *chip) {
  double t = chip->mode == MODE_L ? 16 : 120;
  return t * chip->mtreg / 69.0;
}
static void update(chip_t *chip) {
  if (chip->state != ST_MEASURING_CONT && chip->state != ST_MEASURING_ONCE) return;
  if ((get_sim_nanos() - chip->t_start) / 1e6 < conv_ms(chip)) return;
  double lux = attr_read_float(chip->lux_attr);
  double lpc = (chip->mode == MODE_L ? 4.0 : 1.0) / 1.2 * (69.0 / chip->mtreg) / (chip->mode == MODE_H2 ? 2.0 : 1.0);
  double counts = lux * 1.2 / (1.2 * lpc);
  chip->data = counts > 65535 ? 65535 : (uint16_t)counts;
  chip->t_start = get_sim_nanos();
  if (chip->state == ST_MEASURING_ONCE) chip->state = ST_POWER_DOWN;
}
static bool on_write(void *ud, uint8_t op) {
  chip_t *chip = ud;
  if ((op & 0xFF) == 0x00) { /* power_down */ chip->state = ST_POWER_DOWN; return true; }
  if ((op & 0xFF) == 0x01) { /* power_on */ chip->state = ST_POWER_ON; return true; }
  if ((op & 0xFF) == 0x07) { /* reset */ if (chip->state != ST_POWER_DOWN) chip->data = 0; return true; }
  if ((op & 0xFF) == 0x10) { /* cont_h */ chip->state = ST_MEASURING_CONT; chip->mode = MODE_H; chip->t_start = get_sim_nanos(); return true; }
  if ((op & 0xFF) == 0x11) { /* cont_h2 */ chip->state = ST_MEASURING_CONT; chip->mode = MODE_H2; chip->t_start = get_sim_nanos(); return true; }
  if ((op & 0xFF) == 0x13) { /* cont_l */ chip->state = ST_MEASURING_CONT; chip->mode = MODE_L; chip->t_start = get_sim_nanos(); return true; }
  if ((op & 0xFF) == 0x20) { /* once_h */ chip->state = ST_MEASURING_ONCE; chip->mode = MODE_H; chip->t_start = get_sim_nanos(); return true; }
  if ((op & 0xFF) == 0x21) { /* once_h2 */ chip->state = ST_MEASURING_ONCE; chip->mode = MODE_H2; chip->t_start = get_sim_nanos(); return true; }
  if ((op & 0xFF) == 0x23) { /* once_l */ chip->state = ST_MEASURING_ONCE; chip->mode = MODE_L; chip->t_start = get_sim_nanos(); return true; }
  if ((op & 0xF8) == 0x40) { /* mt_high */ chip->mtreg = (chip->mtreg & 0x1F) | ((op & 7) << 5); return true; }
  if ((op & 0xE0) == 0x60) { /* mt_low */ chip->mtreg = (chip->mtreg & 0xE0) | (op & 0x1F); return true; }
  return false; // undefined opcode → NACK
}
static uint8_t on_read(void *ud) { chip_t *chip = ud; update(chip); return (chip->rd++ & 1) ? (chip->data & 0xFF) : (chip->data >> 8); }
static bool on_connect(void *ud, uint32_t address, bool read) { chip_t *chip = ud; update(chip); chip->rd = 0; return true; }
static void on_disconnect(void *ud) {}

void chip_init(void) {
  chip_t *chip = calloc(1, sizeof(chip_t));
  chip->state = ST_POWER_DOWN; chip->mtreg = 69;
  chip->lux_attr = attr_init_float("lux", 300.0);
  const i2c_config_t cfg = { .user_data = chip, .address = 0x23, .scl = pin_init("SCL", INPUT), .sda = pin_init("SDA", INPUT),
    .connect = on_connect, .read = on_read, .write = on_write, .disconnect = on_disconnect };
  i2c_init(&cfg);
}
