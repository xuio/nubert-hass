# Nubert NuPro

Home Assistant integration for Nubert speakers controlled by the
"Nubert X-Remote" app over Bluetooth LE.

Speakers advertising the nuPro X service (`0000a600-…`) or the X-Sub service
are discovered automatically. nuXero Z2/Z4 and the nuConnect ampXL advertise
generic UUIDs, so add those manually (Settings → Devices & services → Add
integration → Nubert) by picking or typing their Bluetooth address.

The model is read from the speaker after connecting, and only the settings the
official app offers for that model are created.

## Entities

| Platform | Entities |
|---|---|
| Media player | power, volume (with steps), mute, input (per-model input list) |
| Number | bass, mid/high, balance, 5-band EQ, system high-pass, subwoofer crossover, X-Sub low-pass, analog gain (Ceiling/Z), lip sync, LED/lamp brightness, zone wireless level |
| Select | setup role (single/pair/master/slave), channel, analog gain (0/+6 dB), wireless gain, auto-power mode (ampXL), display light/content/colour, wide sound, surround mode, phase (X-Sub/Z1), headphone output, network (ampXL), lamp power mode |
| Switch | loudness, room correction, auto power, zone local/wireless mute, lamp |
| Button | recall/save presets 1–3, identify, Bluetooth pairing/reset, Wi-Fi reset, factory reset (disabled by default) |
| Sensor | master/slave role, model, MCU/DSP/Bluetooth/Wireless/Hardware firmware versions |

Supported models (as named in the app): nuPro X (X2/X4/X6), nuPro X-Sub,
nuPro XS-8500, deCodeX, X-Ceiling speaker, nuConnect, nuConnect ampXL and
nuXero Z1/Z2/Z4. Earlier releases were used with nuPro X speakers and the
X-Sub. The added settings and models come from the reverse-engineered app
protocol (see [PROTOCOL.md](PROTOCOL.md)) and have not been tested on hardware
yet, so please report what works on your model.
