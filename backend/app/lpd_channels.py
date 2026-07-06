"""Справочник LPD (433 МГц) — каналы маломощных раций."""

from dataclasses import dataclass


@dataclass(frozen=True)
class LpdChannel:
  channel: int
  frequency_mhz: float


# LPD433: 69 каналов, шаг 25 кГц, 433.075–434.775 МГц
LPD_CHANNELS: list[LpdChannel] = [
  LpdChannel(channel=n, frequency_mhz=round(433.075 + (n - 1) * 0.025, 3))
  for n in range(1, 70)
]

LPD_BY_CHANNEL: dict[int, LpdChannel] = {c.channel: c for c in LPD_CHANNELS}


def lpd_frequency_mhz(channel: int | None) -> float | None:
  if channel is None:
    return None
  item = LPD_BY_CHANNEL.get(channel)
  return item.frequency_mhz if item else None


def lpd_label(channel: int | None) -> str | None:
  if channel is None:
    return None
  freq = lpd_frequency_mhz(channel)
  if freq is None:
    return None
  return f"LPD {channel} · {freq:.3f} МГц"
