DOMAIN = "nubert"

ADV_UUID = "0000a600-0000-1000-8000-00805f9b34fb"
ADV_UUID_SUB = "ac934713-4019-4441-9387-d53ba93ae21a"

SERVICE_UUID = "8e2ceaaa-0e27-11e7-93ae-92361f002671"
SERVICE_UUID_SPEAKER = "8e2ceaaa-0e27-11e7-93ae-92361f002671"
SERVICE_UUID_SUB = "3c92551f-8448-4636-93e1-12da5274a9a2"

CHAR_UUID = "8e2cece4-0e27-11e7-93ae-92361f002671"
CHAR_UUID_SPEAKER = "8e2cece4-0e27-11e7-93ae-92361f002671"
CHAR_UUID_SUB = "dc968ed5-ed46-43d9-8562-ae5984e55e40"

# Mapping of source IDs to friendly names used by the speakers
SOURCE_NAMES = {
    0x00: "AUX",
    0x02: "XLR",
    0x04: "COAX 1",
    0x05: "COAX 2",
    0x06: "OPTO 1",
    0x07: "OPTO 2",
    0x08: "USB",
    0x09: "PORT",
}

# Sets for simpler membership checks
ADV_UUIDS = {ADV_UUID, ADV_UUID_SUB}
CHAR_UUIDS = {CHAR_UUID_SPEAKER, CHAR_UUID_SUB}

# Mapping of source IDs for regular NuPro speakers
SOURCE_NAMES_SPEAKER = SOURCE_NAMES  # keep backward-compatibility

# Mapping of source IDs for X-Sub – only AUX & WIRELESS are valid and the
# numeric IDs differ from the NuPro mapping
SOURCE_NAMES_SUB = {
    0x00: "AUX",
    0x01: "WIRELESS",
}
