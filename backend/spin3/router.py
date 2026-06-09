from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import os
from spin3.utils import process_factory_summary, calculate_minutes_remaining

router = APIRouter()

# InfluxDB Configuration
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://192.168.2.254:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "dev-machine-token")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "factory")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "machine_raw_v2")

influx_client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG, timeout=30000)
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
    """Returns the last known values and time-to-doff for all machines."""
    fields = [field, "mc_no", "comm_ok", "step", "max_length", "present_length"]
    field_filters = " or ".join([f'r["_field"] == "{f}"' for f in fields])
    
    query = f'''
        latest = from(bucket: "{INFLUXDB_BUCKET}")
            |> range(start: -24h)
            |> filter(fn: (r) => r["_measurement"] == "{measurement}")
            |> filter(fn: (r) => {field_filters})
            |> last()

        delivery = from(bucket: "{INFLUXDB_BUCKET}")
            |> range(start: -30m)
            |> filter(fn: (r) => r["_measurement"] == "{measurement}")
            |> filter(fn: (r) => r["_field"] == "present_length")
            |> derivative(unit: 1m, nonNegative: true)
            |> last()
            |> set(key: "_field", value: "delivery_speed")

        union(tables: [latest, delivery])
    '''
    try:
        tables = query_api.query(query, org=INFLUXDB_ORG)
        
        machine_data = {}

        for table in tables:
            for record in table.records:
                m_id = record.values.get("machine_id")
                if not m_id: continue
                
                if m_id not in machine_data:
                    machine_data[m_id] = {
                        "value": 0.0,
                        "comm_ok": 0,
                        "step": 0,
                        "max_length": 0.0,
                        "present_length": 0.0,
                        "delivery_speed": 0.0,
                        "mc_no": None,
                        "time": record.get_time()
                    }
                
                f_name = record.get_field()
                f_val = record.get_value()
                
                if f_name == field:
                    machine_data[m_id]["value"] = f_val
                elif f_name == "comm_ok":
                    machine_data[m_id]["comm_ok"] = f_val
                elif f_name == "step":
                    machine_data[m_id]["step"] = f_val
                elif f_name == "mc_no":
                    machine_data[m_id]["mc_no"] = f_val
                elif f_name == "max_length":
                    machine_data[m_id]["max_length"] = f_val
                elif f_name == "present_length":
                    machine_data[m_id]["present_length"] = f_val
                elif f_name == "delivery_speed":
                    machine_data[m_id]["delivery_speed"] = f_val
                
                current_time = record.get_time()
                if current_time > machine_data[m_id]["time"]:
                    machine_data[m_id]["time"] = current_time

        results = {}
        for m_id, data in machine_data.items():
            # Calculate minutes remaining
            data["minutes_remaining"] = calculate_minutes_remaining(
                data["present_length"], 
                data["max_length"], 
                data["delivery_speed"]
            )

            mc_val = data["mc_no"]
            if mc_val is not None:
                try: clean_mc = str(int(float(mc_val)))
                except: clean_mc = str(mc_val)
            else:
                clean_mc = str(m_id).replace("rf-", "")
                try: clean_mc = str(int(clean_mc))
                except: pass
            
            results[clean_mc] = data
            
        return results
    except Exception as e:
        import traceback
        print(f"Error in get_machine_status: {str(e)}")
        traceback.print_exc()
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

    # Since mc_no is a field, we can speed up by filtering by machine_id tag if mc_no is provided
    tag_filter = ""
    if mc_no:
        # Prepare machine ID filters (handle padding if numeric)
        mc_id_padded = mc_no
        try:
            if mc_no.isdigit():
                mc_id_padded = f"{int(mc_no):02d}"
        except: pass
        
        # We saw both machine_id (rf-XX) and unit_id (XX) tags in the diagnostic
        tag_filter = f'|> filter(fn: (r) => r["machine_id"] == "rf-{mc_no}" or r["machine_id"] == "rf-{mc_id_padded}" or r["unit_id"] == "{mc_no}" or r["unit_id"] == "{mc_id_padded}")'

    # We use fill() to ensure step and comm_ok are present on rows even if updated at slightly different times
    # We use aggregateWindow for speed profiles to keep data size manageable
    is_speed_profile = "speed" in fields and len(fields) == 1
    
    query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
        |> range({time_range})
        |> filter(fn: (r) => r["_measurement"] == "{measurement}")
        {tag_filter}
        |> filter(fn: (r) => {field_filters} or r["_field"] == "mc_no")
    '''
    
    if is_speed_profile:
        query += '\n        |> aggregateWindow(every: 2m, fn: mean, createEmpty: false)'
        
    query += f'''
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

@router.get("/machine/{mc_no}")
async def get_machine_detail(measurement: str, mc_no: str):
    """Returns the latest values and time-to-doff prediction for a single machine."""
    print(f">>> Fetching machine detail for MC {mc_no} (measurement: {measurement})")
    fields = [
        "speed", "present_length", "max_length", "step", "efficiency", "avg_speed", "ne_y", "comm_ok",
        "shift_1_count", "shift_1_efficiency", "shift_1_stop",
        "shift_2_count", "shift_2_efficiency", "shift_2_stop",
        "shift_3_count", "shift_3_efficiency", "shift_3_stop"
    ]
    
    field_filters = " or ".join([f'r["_field"] == "{f}"' for f in fields])
    
    # Prepare machine ID filters (rf-01, unit_id=1 pattern)
    try:
        mc_int = int(mc_no)
        mc_padded = f"{mc_int:02d}"
        tag_filter = f'|> filter(fn: (r) => r["machine_id"] == "rf-{mc_padded}" or r["unit_id"] == "{mc_int}")'
    except:
        tag_filter = f'|> filter(fn: (r) => r["machine_id"] == "rf-{mc_no}" or r["unit_id"] == "{mc_no}")'

    query = f'''
        data = from(bucket: "{INFLUXDB_BUCKET}")
            |> range(start: -24h)
            |> filter(fn: (r) => r["_measurement"] == "{measurement}")
            {tag_filter}
            |> filter(fn: (r) => {field_filters})

        latest = data |> last()

        delivery = data 
            |> filter(fn: (r) => r["_field"] == "present_length")
            |> range(start: -30m)
            |> derivative(unit: 1m, nonNegative: true)
            |> last()
            |> set(key: "_field", value: "delivery_speed")

        union(tables: [latest, delivery])
    '''
    
    try:
        print(f"Executing query for MC {mc_no}...")
        tables = query_api.query(query, org=INFLUXDB_ORG)
        print(f"Query returned {len(tables)} tables")
        
        if not tables:
            print(f"No data found for MC {mc_no}")
            return {"mc_no": mc_no, "error": "No data found"}
            
        result = {}
        delivery_speed = 0.0
        for table in tables:
            for record in table.records:
                f_name = record.get_field()
                f_val = record.get_value()
                if f_name == "delivery_speed":
                    delivery_speed = f_val
                else:
                    result[f_name] = f_val
                    result["time"] = record.get_time()
        
        # Predictive calculation
        present = result.get("present_length") or 0.0
        max_l = result.get("max_length") or 0.0
        minutes_left = calculate_minutes_remaining(present, max_l, delivery_speed)
        
        result["delivery_speed"] = delivery_speed
        result["minutes_remaining"] = minutes_left
        result["mc_no"] = mc_no
        
        print(f"Successfully processed detail for MC {mc_no}")
        return result
    except Exception as e:
        import traceback
        print(f"!!! Error in get_machine_detail for MC {mc_no}: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/summary")
async def get_factory_summary(measurement: str):
    """Calculates factory-wide KPIs with optimized InfluxDB queries."""
    fields = ["speed", "efficiency", "step", "comm_ok", "shift_1_count", "shift_2_count", "shift_3_count", "max_length", "present_length", "mc_no"]
    field_filters = " or ".join([f'r["_field"] == "{f}"' for f in fields])
    
    # We run two separate optimized queries to avoid scanning 24h of raw data
    latest_query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
            |> range(start: -24h)
            |> filter(fn: (r) => r["_measurement"] == "{measurement}")
            |> filter(fn: (r) => {field_filters})
            |> last()
    '''
    
    # Derivative query only needs the last 30m
    delivery_query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
            |> range(start: -30m)
            |> filter(fn: (r) => r["_measurement"] == "{measurement}")
            |> filter(fn: (r) => r["_field"] == "present_length")
            |> derivative(unit: 1m, nonNegative: true)
            |> last()
            |> set(key: "_field", value: "delivery_speed")
    '''
    
    try:
        # Execute in parallel or sequence
        latest_tables = query_api.query(latest_query, org=INFLUXDB_ORG)
        delivery_tables = query_api.query(delivery_query, org=INFLUXDB_ORG)
        
        # Merge results for processing
        all_tables = latest_tables + delivery_tables
        return process_factory_summary(all_tables)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error in get_factory_summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
