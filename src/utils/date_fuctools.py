from datetime import datetime, timedelta
from loguru import logger


def convert_date_fordays(date_string):
    # 将x天前 转
    days = int(date_string.split(' ')[0])
    types = date_string.split(' ')[1]
    current_date = datetime.now()

    if types == "days" or types == "day":
        delta = timedelta(days=days)
    elif types == "weeks" or types == "week":
        delta = timedelta(weeks=days)
    elif types == "years" or types == "year":
        delta = timedelta(days=days * 365)  # 简单起见，年假设为365天
    elif types == "months" or types == "month":
        delta = timedelta(days=days * 30)
    elif types == "hours" or types == "hour":
        delta = timedelta(hours=days)
    else:
        return current_date.strftime('%Y-%m-%d')

    new_date = (current_date - delta).date()
    new_date = new_date.strftime('%Y-%m-%d')

    return new_date


def convert_date_format(date_str):
    try:
        # 尝试解析为四位年份
        date_object = datetime.strptime(date_str, "%d/%m/%Y")
    except ValueError:
        try:
            # 尝试解析为两位年份
            date_object = datetime.strptime(date_str, "%d/%m/%y")
        except ValueError:
            # 解析失败，返回 None
            return None
    formatted_date = date_object.strftime("%Y-%m-%d %H:%M:%S")

    from dateutil.tz import tzoffset
    dt_utc8 = date_object.replace(tzinfo=tzoffset("UTC+8", 8 * 3600))
    datetime_str = dt_utc8.strftime("%Y-%m-%d %H:%M:%S%z")

    # 格式化日期对象为新的格式
    return formatted_date, datetime_str


def covert_date_edt_type(data_string):
    # 只关注日期不关注时区
    date_obj = datetime.strptime(data_string, "%b %d, %Y, %I:%M %p EDT")
    formatted_date = date_obj.strftime("%Y-%m-%d")

    from dateutil.tz import tzoffset
    dt_utc8 = date_obj.replace(tzinfo=tzoffset("UTC+8", 8 * 3600))
    datetime_str = dt_utc8.strftime("%Y-%m-%d %H:%M:%S%z")

    # 格式化日期对象为新的格式
    return formatted_date, datetime_str


def convert_date_format_en(date_string):
    try:
        # 尝试解析日期字符串格式为 "22 March 2024"
        date_obj = datetime.strptime(date_string, '%d %B %Y')
    except ValueError:
        # 如果解析失败，则尝试解析日期字符串格式为 "March 22, 2024"
        try:
            date_obj = datetime.strptime(date_string, '%B %d, %Y')
        except ValueError:
            try:
                date_obj = datetime.strptime(date_string, '%d %B %Y %H:%M %Z')
            except ValueError:
                try:
                    date_obj = datetime.strptime(date_string, '%d %m %Y')
                except ValueError:
                    return None
    # 将 datetime 对象格式化为包含时间部分的日期时间字符串

    formatted_date_str = date_obj.strftime('%Y-%m-%d')

    from dateutil.tz import tzoffset
    dt_utc8 = date_obj.replace(tzinfo=tzoffset("UTC+8", 8 * 3600))
    datetime_str = dt_utc8.strftime("%Y-%m-%d %H:%M:%S%z")


    return formatted_date_str, datetime_str


def get_previous_date(days: int):
    # 获取当前日期
    try:
        current_date = datetime.now()

        # 计算向前推的日期
        previous_date = (current_date - timedelta(days=days)).date()

        # 格式化日期字符串
        # previous_date_str = previous_date.strftime('%Y-%m-%d')

        return previous_date
    except ValueError as e:
        logger.error(f"日期格式解析错误: {e}")
        return datetime(9999, 1, 1).date()


def date_transform(date_b: str, source_f='%d %b %Y'):
    dt = datetime.strptime(date_b, source_f)
    date_str = dt.strftime('%Y-%m-%d')
    from dateutil.tz import tzoffset
    dt_utc8 = dt.replace(tzinfo=tzoffset("UTC+8", 8 * 3600))
    datetime_str = dt_utc8.strftime("%Y-%m-%d %H:%M:%S%z")
    return date_str, datetime_str

from datetime import datetime


def convert_date_format_slash(date_str, in_format='%Y/%m/%d', out_format='%Y-%m-%d'):
    # 尝试解析日期字符串格式为 "2024/06/16"
    try:
        date_obj = datetime.strptime(date_str, in_format)
        date_str = date_obj.strftime(out_format)

        from dateutil.tz import tzoffset
        dt_utc8 = date_obj.replace(tzinfo=tzoffset("UTC+8", 8 * 3600))
        datetime_str = dt_utc8.strftime("%Y-%m-%d %H:%M:%S%z")
        return date_str, datetime_str
    except ValueError as e:
        print(f"Error converting date: {e}")
        return "Invalid date or format"

# if __name__ == '__main__':
#     days_to_subtract = 3
#     previous_date = get_previous_date(days_to_subtract)
#     print(f"The date {days_to_subtract} days ago was: {previous_date}")
