from datetime import datetime, time, timedelta, timezone

def get_production_day_start(day_start_hour=5, day_start_minute=30):
    """Calculates the datetime for the start of the current production day."""
    local_now = datetime.now()
    day_start_time = time(day_start_hour, day_start_minute)
    
    if local_now.time() >= day_start_time:
        prod_day_start = datetime.combine(local_now.date(), day_start_time)
    else:
        prod_day_start = datetime.combine(local_now.date() - timedelta(days=1), day_start_time)
    
    # Return as aware datetime (matching system local)
    return prod_day_start.astimezone()

def is_current_production_day(ts, prod_day_start):
    """Checks if a given timestamp (ts) is within the current production day."""
    # Ensure both are aware for comparison
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    
    return ts >= prod_day_start

def calculate_minutes_remaining(present, max_l, delivery_speed):
    """Calculates minutes remaining until doffing."""
    if delivery_speed is None or delivery_speed <= 0.1:
        return None
    
    if present is None or max_l is None or present >= max_l:
        return 0
        
    return round((max_l - present) / delivery_speed)

def process_factory_summary(tables, speed_threshold=80, doffing_soon_threshold=10):
    """
    Processes InfluxDB tables to calculate factory-wide KPIs.
    
    Args:
        tables: The query results from InfluxDB query_api.
        speed_threshold: RPM threshold to consider a machine 'Running'.
        doffing_soon_threshold: Minutes remaining to consider a machine 'Doffing Soon'.
        
    Returns:
        dict: A dictionary containing aggregated KPIs.
    """
    prod_day_start = get_production_day_start()
    
    machine_states = {}
    field_timestamps = {} # { (m_id, field): timestamp }

    for table in tables:
        for record in table.records:
            m_id = record.values.get("machine_id")
            if not m_id: continue
            
            if m_id not in machine_states:
                machine_states[m_id] = {}
            
            f_name = record.get_field()
            machine_states[m_id][f_name] = record.get_value()
            field_timestamps[(m_id, f_name)] = record.get_time()

    # Aggregate KPIs
    total_prod = 0.0
    efficiencies = []
    running_count = 0
    doffing_machines = []
    doffing_soon_machines = []
    total_machines = len(machine_states)

    for m_id, state in machine_states.items():
        # Get machine number for display
        mc_no_raw = state.get("mc_no")
        if mc_no_raw is not None:
            try: mc_no = str(int(float(mc_no_raw)))
            except: mc_no = str(mc_no_raw)
        else:
            mc_no = str(m_id).replace("rf-", "")
            try: mc_no = str(int(mc_no))
            except: pass

        # 1. Total Production Calculation
        # Sum shift counts only if they were recorded within the current production day
        for s_field in ["shift_1_count", "shift_2_count", "shift_3_count"]:
            ts = field_timestamps.get((m_id, s_field))
            if ts and is_current_production_day(ts, prod_day_start):
                total_prod += (state.get(s_field) or 0.0)
        
        # 2. Average Efficiency Calculation
        eff = state.get("efficiency")
        if eff is not None:
            eff_ts = field_timestamps.get((m_id, "efficiency"))
            if eff_ts and is_current_production_day(eff_ts, prod_day_start):
                efficiencies.append(eff)
        
        # 3. Running & Doffing Status
        speed_ts = field_timestamps.get((m_id, "speed"))
        if speed_ts and is_current_production_day(speed_ts, prod_day_start):
            speed = state.get("speed") or 0.0
            comm = state.get("comm_ok")
            step = state.get("step")
            
            if step == 6:
                doffing_machines.append(mc_no)
            elif speed > speed_threshold and comm == 1:
                running_count += 1

        # 4. Time-to-Doff Calculation
        delivery_speed = state.get("delivery_speed") or 0.0
        present = state.get("present_length") or 0.0
        max_l = state.get("max_length") or 0.0
        
        minutes_left = calculate_minutes_remaining(present, max_l, delivery_speed)
        
        if minutes_left is not None and 0 < minutes_left <= doffing_soon_threshold:
            doffing_soon_machines.append(mc_no)
        
        # Store back in the machine state if needed
        state["minutes_remaining"] = minutes_left

    return {
        "total_production": round(total_prod, 1),
        "avg_efficiency": round(sum(efficiencies) / len(efficiencies), 1) if efficiencies else 0.0,
        "running_count": running_count,
        "doffing_count": len(doffing_machines),
        "doffing_machines": sorted(doffing_machines, key=lambda x: int(x) if x.isdigit() else x),
        "doffing_soon_count": len(doffing_soon_machines),
        "doffing_soon_machines": sorted(doffing_soon_machines, key=lambda x: int(x) if x.isdigit() else x),
        "total_machines": total_machines,
        "production_day_start": prod_day_start.isoformat()
    }
