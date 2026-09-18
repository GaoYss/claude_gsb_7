"""日期解析与序列化辅助。"""

from datetime import date, datetime, timedelta


def parse_date(value, field_label="日期"):
    """把 YYYY-MM-DD 或 ISO 字符串解析为 date。"""

    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(text).date()
        except ValueError as exc:
            raise ValueError(f"{field_label}格式应为 YYYY-MM-DD") from exc
    raise ValueError(f"{field_label}格式应为 YYYY-MM-DD")


def format_date(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return None


def format_datetime(value):
    if isinstance(value, datetime):
        return value.replace(microsecond=0).isoformat(sep=" ")
    return None


def today():
    return datetime.now().date()


def add_months(value, months):
    """日期按月偏移（月底日期自动回退到目标月最后一天），用于质保期推算。"""

    month_index = value.year * 12 + (value.month - 1) + months
    year, month = divmod(month_index, 12)
    month += 1
    if month == 12:
        last_day = date(year, 12, 31)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)
    return date(year, month, min(value.day, last_day.day))
