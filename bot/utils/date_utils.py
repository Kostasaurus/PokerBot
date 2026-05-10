from datetime import datetime
from typing import Tuple
from zoneinfo import ZoneInfo

MONTHS_NOMINATIVE = {
    1: "январь",
    2: "февраль",
    3: "март",
    4: "апрель",
    5: "май",
    6: "июнь",
    7: "июль",
    8: "август",
    9: "сентябрь",
    10: "октябрь",
    11: "ноябрь",
    12: "декабрь"
}

MONTHS_GENITIVE = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря"
}

QUARTERS_NOMINATIVE = {
    1: '1 квартал',
    2: '2 квартал',
    3: '3 квартал',
    4: '4 квартал',
}


MOSCOW_TZ = ZoneInfo("Europe/Moscow")




def format_datetime_moscow(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))

    moscow_dt = dt.astimezone(MOSCOW_TZ)

    return f"{moscow_dt.day} {MONTHS_GENITIVE[moscow_dt.month]} в {moscow_dt.strftime('%H:%M')}"


def format_date_short_moscow(dt: datetime) -> str:

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))

    moscow_dt = dt.astimezone(MOSCOW_TZ)
    return f"{moscow_dt.day:02d}.{moscow_dt.month:02d}"

def get_date_range_for_year(year: int):
    start = datetime(year, 1, 1)
    end = datetime(year + 1, 1, 1)
    return start, end

def get_date_range_for_month(year: int, month: int):
    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, month + 1, 1)
    return start, end

def get_quarter_range(year: int, quarter: int) -> Tuple[datetime, datetime]:
    if quarter == 1:
        start = datetime(year, 1, 1)
        end = datetime(year, 4, 1)
    elif quarter == 2:
        start = datetime(year, 4, 1)
        end = datetime(year, 7, 1)
    elif quarter == 3:
        start = datetime(year, 7, 1)
        end = datetime(year, 10, 1)
    else:
        start = datetime(year, 10, 1)
        end = datetime(year + 1, 1, 1)
    return start, end

def get_current_quarter() -> Tuple[int, int]:
    now = datetime.now()
    quarter = (now.month - 1) // 3 + 1
    return now.year, quarter