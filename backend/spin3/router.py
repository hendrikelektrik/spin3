from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import os

router = APIRouter()

# InfluxDB Configuration
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://192.168.2.254:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "dev-machine-token")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "factory")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "machine_raw_v2")

influx_client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
query_api = influx_client.query_api()

# Mock user database for Spin3
users_db = {
    "admin": {
        "username": "admin",
        "password": "password",
        "full_name": "Administrator"
    }
}

class LoginRequest(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    username: str
    full_name: str

@router.post("/login", response_model=UserResponse)
def login(request: LoginRequest):
    print(f"Login attempt for: {request.username}")
    user = users_db.get(request.username)
    if user and user["password"] == request.password:
        return {
            "username": user["username"],
            "full_name": user["full_name"]
        }
    print(f"Login failed for: {request.username}")
    raise HTTPException(status_code=401, detail="Invalid credentials")

@router.get("/discover")
async def discover_schema():
    """Returns a list of measurements and their fields in the bucket."""
    print(f"Discovering schema for bucket: {INFLUXDB_BUCKET}")
    
    # Query to get all measurements
    measurements_query = f'import "influxdata/influxdb/schema" schema.measurements(bucket: "{INFLUXDB_BUCKET}")'
    
    try:
        m_tables = query_api.query(measurements_query, org=INFLUXDB_ORG)
        schema = {}
        
        found_measurements = []
        for table in m_tables:
            for record in table.records:
                m_name = record.get_value()
                if m_name:
                    found_measurements.append(m_name)
        
        print(f"Found measurements: {found_measurements}")
        
        if not found_measurements:
            return {"message": "No measurements found in the last 24h or bucket is empty", "schema": {}}

        for measurement in found_measurements:
            # Query to get fields for this measurement - searching last 30 days to be safe
            fields_query = f'''
                from(bucket: "{INFLUXDB_BUCKET}")
                |> range(start: -30d)
                |> filter(fn: (r) => r["_measurement"] == "{measurement}")
                |> keep(columns: ["_field"])
                |> group()
                |> distinct(column: "_field")
            '''
            f_tables = query_api.query(fields_query, org=INFLUXDB_ORG)
            fields = []
            for f_table in f_tables:
                for f_record in f_table.records:
                    f_name = f_record.get_value()
                    if f_name:
                        fields.append(f_name)
            schema[measurement] = fields
        
        return schema
    except Exception as e:
        import traceback
        print(f"Error in discover_schema: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"InfluxDB Error: {str(e)}")

@router.get("/status")
async def get_machine_status(measurement: str, field: str):
    """Returns the last known values for all machines, including comm_ok and step."""
    # Since mc_no is a field, pivot first, then group by the new mc_no column
    query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
        |> range(start: -24h)
        |> filter(fn: (r) => r["_measurement"] == "{measurement}")
        |> filter(fn: (r) => r["_field"] == "{field}" or r["_field"] == "mc_no" or r["_field"] == "comm_ok" or r["_field"] == "step")
        |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        |> fill(column: "comm_ok", usePrevious: true)
        |> fill(column: "step", usePrevious: true)
        |> group(columns: ["mc_no"])
        |> last(column: "_time")
    '''
    try:
        print(f"Executing status query for {measurement}.{field}")
        tables = query_api.query(query, org=INFLUXDB_ORG)
        results = {}
        for table in tables:
            for record in table.records:
                mc_val = record.values.get("mc_no")
                speed_val = record.values.get(field)
                comm_ok_val = record.values.get("comm_ok")
                step_val = record.values.get("step")
                
                if mc_val is not None:
                    try:
                        # Normalize mc_no (e.g., 1.0 -> "1")
                        clean_mc = str(int(float(mc_val)))
                    except:
                        clean_mc = str(mc_val)
                    
                    # Debug log to verify values
                    print(f"Machine {clean_mc}: speed={speed_val}, comm_ok={comm_ok_val}, step={step_val}")
                        
                    results[clean_mc] = {
                        "value": speed_val if speed_val is not None else 0.0,
                        "comm_ok": comm_ok_val if comm_ok_val is not None else 0,
                        "step": step_val if step_val is not None else 0,
                        "time": record.get_time()
                    }
        print(f"Backend found data for {len(results)} machines")
        return results
    except Exception as e:
        print(f"Error in get_machine_status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/telemetry")
async def get_telemetry(
    measurement: str, 
    field: str, 
    mc_no: Optional[str] = None, 
    range_h: Optional[int] = 1,
    start: Optional[str] = None,
    end: Optional[str] = None
):
    """Returns historical data for a specific machine and field(s). Supports relative (range_h) or absolute (start, end) ranges."""
    # Support multiple fields separated by comma
    fields = field.split(",")
    field_filters = " or ".join([f'r["_field"] == "{f}"' for f in fields])
    
    # Determine the time range for the Flux query
    if start and end:
        # Absolute range: start and end should be RFC3339 strings
        time_range = f'start: {start}, stop: {end}'
    elif start:
        # Just start
        time_range = f'start: {start}'
    else:
        # Relative range (default)
        time_range = f'start: -{range_h}h'

    # Since mc_no is a field, we pivot first, then filter in Python to be safe with types
    # We use fill() to ensure step and comm_ok are present on rows even if updated at slightly different times
    query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
        |> range({time_range})
        |> filter(fn: (r) => r["_measurement"] == "{measurement}")
        |> filter(fn: (r) => {field_filters} or r["_field"] == "mc_no")
        |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        |> fill(column: "comm_ok", usePrevious: true)
        |> fill(column: "step", usePrevious: true)
        |> drop(columns: ["_start", "_stop", "_measurement"])
    '''
        
    try:
        tables = query_api.query(query, org=INFLUXDB_ORG)
        results = []
        for table in tables:
            for record in table.records:
                # Normalize mc_no from the record
                rec_mc = record.values.get("mc_no")
                if rec_mc is not None:
                    try:
                        clean_rec_mc = str(int(float(rec_mc)))
                    except:
                        clean_rec_mc = str(rec_mc)
                    
                    # Only include if it matches the requested mc_no
                    if mc_no and clean_rec_mc != mc_no:
                        continue
                elif mc_no:
                    # If we requested a specific machine but this row has no mc_no, skip it
                    continue

                data_point = {"time": record.get_time()}
                if not mc_no:
                    data_point["mc_no"] = clean_rec_mc
                    
                # Extract all requested fields
                for f in fields:
                    val = record.values.get(f)
                    data_point[f] = val if val is not None else 0.0
                results.append(data_point)
        
        print(f"Telemetry query returned {len(results)} points for MC {mc_no}")
        return results
    except Exception as e:
        print(f"Error in get_telemetry: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
