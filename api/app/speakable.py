"""Speakable times for Gujarati / Hindi / English. Never return 17:00 to the agent."""

from datetime import datetime

_NUM_EN = {
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
    10: "ten",
    11: "eleven",
    12: "twelve",
}

_NUM_GU = {
    1: "ek",
    2: "be",
    3: "tran",
    4: "chaar",
    5: "paanch",
    6: "chha",
    7: "saat",
    8: "aath",
    9: "nav",
    10: "das",
    11: "agiyar",
    12: "baar",
}

_NUM_HI = {
    1: "ek",
    2: "do",
    3: "teen",
    4: "chaar",
    5: "paanch",
    6: "chhe",
    7: "saat",
    8: "aath",
    9: "nau",
    10: "das",
    11: "gyaarah",
    12: "baarah",
}

_WEEKDAY_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_WEEKDAY_GU = ["Somvaar", "Mangalvaar", "Budhvaar", "Guruvaar", "Shukravaar", "Shanivaar", "Ravivaar"]
_WEEKDAY_HI = ["Somvaar", "Mangalvaar", "Budhvaar", "Guruvaar", "Shukravaar", "Shanivaar", "Ravivaar"]


def _hour12(dt: datetime) -> int:
    h = dt.hour % 12
    return 12 if h == 0 else h


def _period(dt: datetime) -> str:
    if dt.hour < 12:
        return "morning"
    if dt.hour < 16:
        return "afternoon"
    if dt.hour < 20:
        return "evening"
    return "night"


def speak_time(dt: datetime, language: str = "en") -> str:
    lang = (language or "en")[:2].lower()
    h = _hour12(dt)
    period = _period(dt)
    minute = dt.minute
    if lang == "gu":
        num = _NUM_GU.get(h, str(h))
        if period == "morning":
            base = f"subah na {num} vaagy"
        elif period == "afternoon":
            base = f"bapore na {num} vaagy"
        elif period == "evening":
            base = f"shaame na {num} vaagy"
        else:
            base = f"raatre na {num} vaagy"
        if minute:
            base += f" {minute} minute"
        return base
    if lang == "hi":
        num = _NUM_HI.get(h, str(h))
        if period == "morning":
            base = f"subah ke {num} baje"
        elif period == "afternoon":
            base = f"dopahar ke {num} baje"
        elif period == "evening":
            base = f"shaam ke {num} baje"
        else:
            base = f"raat ke {num} baje"
        if minute:
            base += f" {minute} minute"
        return base
    num = _NUM_EN.get(h, str(h))
    if minute:
        return f"{num} {minute} in the {period}"
    return f"{num} in the {period}"


def speak_day(dt: datetime, language: str = "en") -> str:
    lang = (language or "en")[:2].lower()
    idx = dt.weekday()
    if lang == "gu":
        return _WEEKDAY_GU[idx]
    if lang == "hi":
        return _WEEKDAY_HI[idx]
    return _WEEKDAY_EN[idx]


def slot_id(doctor_id: int, slot_start: datetime) -> str:
    return f"{doctor_id}:{slot_start.strftime('%Y%m%dT%H%M')}"


def parse_slot_id(value: str) -> tuple[int, datetime]:
    doctor_s, ts = value.split(":", 1)
    return int(doctor_s), datetime.strptime(ts, "%Y%m%dT%H%M")
