# Nubert BLE protocol

Reverse engineered from the official **Nubert X-Remote** Android app
(`com.nupro`, version 2.0.48, `com.nupro.apk` SHA-256
`77de5243f9964ac61a8a86efd91d323d7f6cb9501b44b3f3a86a1b9db692abc4`) by static
decompilation with JADX. Nothing here was captured from a live speaker. The
value ranges and labels come from the app's UI code, so treat them as what the
app sends, not as a firmware specification.

Main classes: `com.nupro.protocol.NuproProtocol` (command ids),
`com.nupro.service.BluetoothLeService` (GATT, notification dispatch),
`com.nupro.events.InformEvents` (response parsers),
`com.nupro.utils.CommonUtil` / `menuView` (model and label tables) and the
`activity.*` classes (value ranges).

## Transport

| Product family | Advertised UUID | GATT service | Write char | Notify char | Write type |
|---|---|---|---|---|---|
| nuPro X, X-Ceiling, XS-8500, deCodeX, nuConnect | `0000a600-…` | `8e2ceaaa-0e27-11e7-93ae-92361f002671` | `8e2cece4-…` | same | with response |
| X-Sub, Z1 ("X1" family) | `ac934713-4019-4441-9387-d53ba93ae21a` | `3c92551f-8448-4636-93e1-12da5274a9a2` | `dc968ed5-…` | same | **without** response |
| nuXero Z2/Z4 (old) | `0000fff0-…` | `0000fff0-…` | `0000fff1-…` | `0000fff2-…` | with response |
| nuXero Z2/Z4 (new) | `0000fff1-…` | `0000fff1-…` | `0000fff2-…` | `0000fff3-…` | with response |
| nuConnect ampXL | `0000e010-…` | `0000e010-…` | `0000e012-…` | `0000e011-…` | with response |

Notifications are enabled through the usual `0x2902` CCCD.

## Framing

```
[cmd][len][payload × len]
```

Each SET is one frame, e.g. `0B 01 50` sets volume to raw 0x50.

Reads are batched. Old devices use `40 <n> <get ids…>` and new devices use
`86 <n> <get ids…>`. The speaker then answers with notifications that start
with the GET id, e.g. `0A 01 50`. Answers to `0x86` arrive wrapped as
`86 <len> <frame><frame>…`. A few GETs are sent bare, e.g. `66` or `88 00`.

"New type" comes from the `0x4C` response (see below). The app uses `0x86`
whenever it is set.

## Device identification (`0x4C` IS_SLAVE)

Payload: `[slave][type][flag][…]`

* `slave`: 0 = master/standalone, 1 or 2 = slave (the app locks its UI).
* `type` (missing ⇒ `00`):

| type | model | | type | model |
|---|---|---|---|---|
| 00 | X2 (nuPro X) | | 07 | deCodeX |
| 01 | X4 (nuPro X) | | 08 | XS-8500 |
| 02, 03 | X-Sub | | 09 | nuXero Z2 |
| 04 | X6 | | 0A | nuXero Z4 |
| 05 | nuConnect | | 0D | nuConnect ampXL |
| 06 | X-Ceiling speaker | | 0E | Z1 |

* New-type: for types 00/01 it is `flag == 01`. Type 03 is old type. Every
  other type is new type.
* Room calibration is allowed for types 00/01 only when the payload is at
  least 4 bytes long, and always for the other types.
* `C6` (NEW_X2_X4) returns a version byte. At 36 or above, nuConnect gains the
  extended channel options and the named wide-sound modes.

## Commands

GET responses use the GET id. Unless noted, the payload is one byte and the
SET payload has the same encoding.

| Function | GET | SET | Encoding | Models (per app UI) |
|---|---|---|---|---|
| Firmware versions | 02 (`02 00`) | – | response `02 len kind ascii…`; kind 0 MCU, 1 DSP, 2 Bluetooth, 3 Wireless, 4 Hardware | all |
| Device (BLE) name | – | 05 | ASCII bytes | all |
| Factory reset | – | 07 | 1 = reset, 0 = cancel | all |
| Serial number | 08 | – | (unused by app) | |
| Volume | 0A | 0B | main: 0–100 ⇒ −100…0 dB; X-Sub: 0–21 ⇒ −15…+6 dB; Z1: 0–20 ⇒ −14…+6 dB | all |
| Input | 0E | 0F | index, see input table; ampXL adds a 2nd byte = network source (1 AirPlay, 2 DMR, 3 DMP, 4 Spotify, 24 Google) | all |
| 5-band EQ | 10 | 11 | GET → 5 bytes (60 Hz, 240 Hz, 1 kHz, 3.5 kHz, 16 kHz), raw 0–12 ⇒ −6…+6 dB; SET `[band, raw]` | main except deCodeX |
| Auto power | 1A | 1B | 0 off, 1 on; ampXL: 0 auto-off, 1 deep standby, 2 network standby | all |
| Power | 1E | 1F | 0 = on, 1 = standby | all |
| Bass | 20 | 21 | 0–40 ⇒ −10…+10 dB (0.5 dB) | main |
| Mid/high | 22 | 23 | as bass | main |
| Balance | 24 | 25 | 0–40, 20 = centre, >20 attenuates left | main except Ceiling, deCodeX |
| System high-pass | 26 | 27 | raw = Hz, 10–140 | main except deCodeX |
| Subwoofer crossover | 28 | 29 | main: raw = Hz, 20–140; X-Sub/Z1 low-pass: 0–21 ⇒ 35 + 5·raw Hz | X2/X4/X6/nuConnect/ampXL, X1 family |
| Loudness | 2A | 2B | 0/1 | main |
| Bluetooth | – | 2F | 0 = enter pairing, 1 = reset Bluetooth | main except Z2/Z4 |
| Analog gain | 32 | 33 | X/XS/nuConnect/ampXL: 0 = 0 dB, 1 = +6 dB; Ceiling/Z2/Z4: 0–20 ⇒ −10…+10 dB | |
| Setup (multi-speaker role) | 34 | 35 | X2/X4/Z2/Z4: 0 single, 1 pair, 2 master, 3 slave; X6/nuConnect/ampXL/XS-8500/deCodeX: 0 single, 1 master, 2 slave; Ceiling: 0 single, 3 master, 6 slave; X1: 0 unlinked, 3 paired | all |
| Channel | 36 | 37 | X2/X4/Z: 0 L, 1 R, 2 mono; X6 & old nuConnect: 0 stereo, 1 mono; ampXL & nuConnect ≥ 36: 0 L, 1 R, 2 mono, 4 mute, 5 stereo; Ceiling adds 3/4 Atmos height L/R; XS-8500: 0–7 surround/back/height pairs. GET values ≥ 16 carry a type in the high nibble (use `raw % 16`) | main |
| Channel config | 38 | 41 | `[checked, device]` | XS-8500, deCodeX |
| Channel device | 39 | – | `[channel, device, name…]` | |
| Batched read (old) | 40 | – | `40 n ids…` | |
| Display content | 42 | 43 | 0 volume, 1 logo | not Z, not Ceiling |
| Display light | 44 | 45 | 0 normal, 1 auto dim, 2 auto off | not Ceiling |
| Save preset | – | 47 | 1–3 | all |
| Preset recalled (notify) | 48 | – | 1–3 | |
| Recall preset | – | 49 | 1–3 | all |
| Mute | 4A | 4B | 0/1 | all |
| Is slave / model | 4C | – | see above | all |
| Connect indication | – | 4D | 1 = connected (LED), 0 = disconnecting | all |
| Wireless gain | 4F | 4E | 0–6 ⇒ 0…−18 dB (3 dB steps) | ampXL |
| Distance | 50 | 51 | `[channel, raw]`, raw 5–120 | deCodeX |
| Crossover | 52 | 53 | `[channel, raw]` | deCodeX |
| Lamp on/off | 58 | 59 | 0/1 | Ceiling |
| Brightness | 60 | 61 | 0–100 % (LED/lamp) | main |
| Lamp power mode | 62 | 63 | 0 independent, 1 synchronized | Ceiling |
| Zigbee pair | 64 | 65 | | Ceiling |
| Network | 66 | 67 | 0 ethernet, 1 Wi-Fi, 2 Wi-Fi reset | ampXL |
| Headphone | 68 | 69 | 0 exclusive, 1 paralleled | ampXL |
| DSP update | 72 | 73 | 1 = update available / start | |
| Wide sound | 74 | 75 | 0 stereo, 1 voice+, 2 wide normal, 3 wide mid, 4 wide large | X6, nuConnect, ampXL |
| Zone local mute | 76 | 77 | 0/1 | X6, nuConnect |
| Zone wireless mute | 78 | 79 | 0/1 | X6, nuConnect |
| Zone slave | 80 | – | 1 = zone control available | X6, nuConnect |
| Password | 82 | 83 | 4 bytes, one digit each (checked only by the app) | |
| Room EQ points | 84 | 85 | calibration curve transfer | |
| Batched read (new) | 86 | – | `86 n ids…` | |
| Zone wireless level | 88 | 89 | 1–21 ⇒ −10…+10 dB | X6, nuConnect |
| Surround system | 91 | 92 | `[device, value]` | XS-8500, deCodeX |
| Surround mode | 93 | 94 | 0 stereo, 1 movie, 2 music, 3 voice+, 4 night, 5 auto, 6 party (deCodeX only) | XS-8500, deCodeX |
| Lip sync | 95 | 96 | 0–40 ⇒ 0–400 ms | XS-8500, deCodeX |
| DSP debug | A0 | A1 | 0/1 | |
| Phase | A4 | A5 | 0 = 0°, 1 = 180° | X-Sub, Z1 |
| Noise switch | A8 | A9 | `[device, on]` | |
| Slave devices | C0 | C1 | | |
| X2/X4 version | C6 | – | version byte | |
| Room EQ | E4 | E5 | 0/1 | when allowed |
| Room EQ value | – | E3 | calibration upload | |
| Pink noise | E6 | E7 | 0/1 | |
| Display colour | E8 | E9 | 0 source colour, 1 white | Z1, Z2/Z4 (MCU ≥ 2.58) |

## Inputs (`menuView.initInputView`)

| idx | X2/X4 | X6 | nuConnect | ampXL | XS-8500 | deCodeX | Z2/Z4 | Ceiling | X-Sub | Z1 |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | AUX | AUX | AUX | AUX | HDMI | eARC | AUX | – | AUX | AUX |
| 1 | Bluetooth | Bluetooth | Bluetooth | Bluetooth | AUX | HDMI 1 | XLR | Bluetooth | Wireless | XLR |
| 2 | XLR | Wireless | Wireless | Wireless | Bluetooth | HDMI 2 | AES | Wireless | | Wireless |
| 3 | AES | Coax 1 | Phono | Network | Coax 1 | HDMI 3 | Coax 1 | Balanced | | |
| 4 | Coax 1 | Coax 2 | Coax 1 | Phono | Coax 2 | AUX | Coax 2 | AES | | |
| 5 | Coax 2 | Opt 1 | Coax 2 | Coax 1 | Opt 1 | Bluetooth | | | | |
| 6 | Opt 1 | Opt 2 | Opt 1 | Coax 2 | Opt 2 | Coax | | | | |
| 7 | Opt 2 | USB | Opt 2 | Opt 1 | Port | Optical | | | | |
| 8 | USB | Port | USB | Opt 2 | | Port | | | | |
| 9 | Port | | Port | USB | | | | | | |
| 10 | | | | Port | | | | | | |

## Not implemented in the HA integration

Room-calibration measurement (`84/85/E3`, needs the phone microphone),
multi-room slave management (`C0/C1/C5/97/98`), per-channel distance/crossover
and channel configuration for deCodeX/XS-8500, surround-system noise tests,
DSP firmware update, password lock (app-side only), Zigbee pairing and device
renaming.
