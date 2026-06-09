from influxdb_client import InfluxDBClient
import os

INFLUXDB_URL = "http://192.168.2.254:8086"
INFLUXDB_TOKEN = "dev-machine-token"
INFLUXDB_ORG = "factory"
INFLUXDB_BUCKET = "machine_raw_v2"

client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
query_api = client.query_api()

query = f'''
    from(bucket: "{INFLUXDB_BUCKET}")
    |> range(start: -1h)
    |> filter(fn: (r) => r["_measurement"] == "machine_telemetry")
    |> filter(fn: (r) => r["_field"] == "speed")
    |> group()
    |> limit(n: 5)
'''

tables = query_api.query(query)
for table in tables:
    for record in table.records:
        print(f"Time: {record.get_time()}, Tags: {record.values}, Value: {record.get_value()}")
