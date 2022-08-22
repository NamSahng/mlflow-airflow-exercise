INDEX_UNIQUE = False


def _get_mongo_client():
    """Get mongo client."""
    import os

    from pymongo import MongoClient

    user = os.getenv("MONGODB_USER")
    pwd = os.getenv("MONGODB_PWD")
    host = os.getenv("MONGODB_HOST")
    port = os.getenv("MONGODB_PORT")
    client = MongoClient(f"mongodb://{user}:{pwd}@{host}:{port}")
    return client


def insert_ohlcvs(templates_dict, **context):
    """Insert fetched Upbit OHLCV data into mongodb."""
    import logging

    from de.utils.timeutils import UTC, get_datetime_from_ts, json_strptime

    logger = logging.getLogger(__name__)

    start_time = templates_dict["start_time"]
    db_name = templates_dict["db_name"]
    utc_time = get_datetime_from_ts(start_time, get_day_before=False, tz=UTC)

    logger.info(start_time)
    logger.info(utc_time)

    prev_task_id = next(iter(context["task"].upstream_task_ids))
    json_dicts = context["task_instance"].xcom_pull(task_ids=prev_task_id)
    json_dicts = json_strptime(json_dicts)
    ticker = json_dicts[0]["market"]
    logger.info(json_dicts)

    for d in json_dicts:
        # 동부시간의 서머타임으로 인해 서머타임 해제 시, 시간이 중복되기 때문에 etz_time은 인덱스가 될 수 없음
        # 업비트 서버점검으로 인해 candle_date_time_utc는 인덱스가 될 수 없음(겹침)
        # => DAG의 실행시간을 collection index로 설정
        # TODO: 2개 이상을 불러 올 때는 utc_time을 time interval씩 더해서 넣어줘야 함.
        d.update({"utc_time": utc_time})

    # Get database
    mongo_client = _get_mongo_client()
    db = mongo_client[db_name]

    # Make collection
    if ticker not in db.list_collection_names():
        try:
            db.create_collection(ticker)
            db[ticker].create_index([("utc_time", 1)], unique=INDEX_UNIQUE)
        except Exception as e:
            logger.info(e)

    db[ticker].insert_many(json_dicts)

    mongo_client.close()


def insert_single(templates_dict, **context):
    """Insert fetched google news or FRED data into MongoDB."""
    import logging

    from de.utils.timeutils import get_datetime_from_ts

    logger = logging.getLogger(__name__)
    start_time = templates_dict["start_time"]
    db_name = templates_dict["db_name"]
    collection_name = templates_dict["collection_name"]
    etz_time = get_datetime_from_ts(start_time, get_day_before=True)

    logger.info(start_time)
    logger.info(etz_time)

    prev_task_id = next(iter(context["task"].upstream_task_ids))
    single_dict = context["task_instance"].xcom_pull(task_ids=prev_task_id)
    single_dict.update(etz_time=etz_time)
    # Get database
    mongo_client = _get_mongo_client()
    db = mongo_client[db_name]
    if collection_name not in db.list_collection_names():
        try:
            db.create_collection(collection_name)
            db[collection_name].create_index([("etz_time", 1)], unique=INDEX_UNIQUE)
        except Exception as e:
            logger.info(e)

    db[collection_name].insert_one(single_dict)

    mongo_client.close()
