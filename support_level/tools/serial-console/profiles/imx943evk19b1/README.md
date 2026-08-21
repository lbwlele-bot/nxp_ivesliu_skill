# i.MX943 19x19 B1 EVK Serial Profile

## Identity and scope

- EVK board revision: B1
- SoC revision observed in EEPROM: A0
- Observed FTDI serial: `0C1819` (evidence only; the profile does not hard-code it)
- Adapter: onboard `0403:6011` FT4232H, four interfaces
- Serial format: `115200 8N1`
- Current profile status: `partial`

The BCU board token follows the EVK revision, so this board uses
`imx943evk19b1`. It must not be selected from the SoC A0 revision.

## Onboard mapping

| Order | Interface | Role | Current evidence |
|---|---|---|---|
| 1 | `if00` | `first-com` | User identifies application M33; runtime bytes not yet captured |
| 2 | `if01` | `second-com` | Verified BCU control channel |
| 3 | `if02` | `a-core` | Verified SPL/BL31/U-Boot/RTE Linux console |
| 4 | `if03` | `sm` | Verified DDR OEI/SMFW/monitor console |

Default capture selects the verified `a-core` and `sm` roles. The overall
profile remains `partial` only because the application-M33 role on `if00`
still lacks captured runtime evidence.

## BCU interaction

This B1 board requires SW7-1 `OFF` for BCU operation. The following combination
was verified on 2026-08-07:

```bash
sudo -n bcu eeprom -r -auto
sudo -n bcu get_boot_mode -auto
sudo -n bcu reset -auto
```

The EEPROM auto path was rechecked on 2026-08-21. It returned board token
`imx943evk19b1`, Board Rev B1, SoC Rev A0 and PMIC MFS5600. Do not derive the
board token from the SoC revision or replace `-auto` with an LLM-selected
`-board=` value.

EEPROM reads and other BCU access use `if01` and can detach it from `ftdi_sio`.
Complete identity detection before capture, then restore it with:

```bash
sudo -n ./serial-console recover --board imx943evk19b1
./serial-console probe --board imx943evk19b1
```

For reset-start logs, start `capture-set` after this recovery and wait for
`ALL PORTS READY` before issuing the BCU reset.

## External M7 UARTs

The two external CH340 USB-to-TTL adapters are not part of this onboard
profile. Their stable host paths and verified CM70/CM71 assignment are recorded
in the source case `records/SERIAL_TOPOLOGY.md`.

## Evidence

- Source case: `2026-08-06-imx943-dual-m7-udp-rpmsg-latency`
- B1 EEPROM and reset record: `logs/2026-08-07-b1-bcu-reset.txt`
- Serial session: `logs/rte34-sd-forced-boot-serial-session.yaml`
- `if02` captured the full A-core boot through the RTE 3.4 login prompt.
- `if03` captured DDR OEI completion and the SMFW monitor prompt.
