import re
import os
import json
import requests as http_requests
from langchain.tools import tool
from sqlalchemy import text

PLATE_NUMBER_REGEX = re.compile(
    r'^[A-Z]{1,2}\s[0-9]{1,4}\s[A-Z]{1,3}$',
    re.IGNORECASE
)

def validate_plate_number(plate: str) -> tuple[bool, str]:
    """Validasi format plat nomor Indonesia. Return (is_valid, pesan_error)."""
    if not plate or not isinstance(plate, str):
        return False, "Nomor plat tidak boleh kosong."
    plate_stripped = plate.strip()
    if not PLATE_NUMBER_REGEX.match(plate_stripped):
        return False, (
            f"Format nomor plat '{plate_stripped}' tidak valid."
        )
    return True, ""

def use_tools(db):
    """
    Buat dan return list tools LangChain.
    Parameter db: instance SQLDatabase dari main.py.
    """

    @tool
    def system_control(action_type: str = "NAVIGATE", target_page: str = "dashboard", data: dict = None) -> dict:
        """
        VERY IMPORTANT: Use this tool for navigation or system actions.
        For navigating to detail pages (like detail_location), pass the entity's ID in `data`, e.g., data={"id": 123}.
        """
        try:
            return {
                "ui_action": action_type,
                "target": target_page,
                "data": data,
                "message": f"Mengarahkan Anda ke halaman {target_page.replace('_', ' ')}..."
            }
        except Exception:
            return {
                "ui_action": "NAVIGATE",
                "target": "dashboard",
                "message": "Terjadi kesalahan navigasi."
            }

    @tool
    def get_available_options(query: str | dict = "") -> str:
        """
        Fetches available dropdown options for trucks and locations:
        - Vehicle Types (name and id)
        - Distribution Centers (name and id)
        - Customers (name and id)
        - Valid Statuses (TruckFirstStatus and TruckSecondStatus)
        Use this before creating or updating a truck or location to ensure you have the correct IDs and enum values.
        """
        try:
            types     = db.run("SELECT id, name FROM truck_type")
            dcs       = db.run("SELECT id, name FROM dc")
            customers = db.run("SELECT id, name FROM customer")

            first_statuses  = ["AVAILABLE", "UNAVAILABLE"]
            second_statuses = ["ON_DELIVERY", "OUT_OF_STOCK", "ARCHIVE", "MAINTENANCE", "LEGAL"]

            result = {
                "vehicle_types":        types,
                "distribution_centers": dcs,
                "customers":            customers,
                "first_statuses":       first_statuses,
                "second_statuses":      second_statuses,
            }
            return json.dumps(result)
        except Exception as e:
            return f"Error fetching options: {str(e)}"

    @tool
    def manage_truck(query: dict | str) -> dict:
        """
        Use this tool for CREATE, UPDATE, or DELETE operations on truck entities.
        Input must be a JSON string with:
        - action: 'CREATE', 'UPDATE', or 'DELETE'
        - data: dictionary of truck fields (for UPDATE/DELETE), or LIST of truck dicts (for CREATE).
        For CREATE: data must be a LIST of truck objects. Requires plate_number, type_id (or type_name), dc_id (or dc_name), max_individual_capacity_volume, first_status
          Use this when user wants to create one or more trucks.
          You can provide 'type_name' instead of 'type_id', and 'dc_name' instead of 'dc_id'.
          IMPORTANT: plate_number MUST follow Indonesian license plate format:
          [1-2 letter area code] [1-4 digit registration number] [1-3 letter series code]
          Each part separated by a SINGLE SPACE. Example: "B 1234 RFS", "AB 12 CD".
          Example: {"action": "CREATE", "data": [{"plate_number": "B 1234 AB", "type_name": "Blind Van", "dc_name": "DC Jakarta", "max_individual_capacity_volume": 1500000, "first_status": "AVAILABLE"}]}
        For UPDATE/DELETE: requires plate_number or id.
        """
        try:
            payload = query if isinstance(query, dict) else json.loads(query)
            action  = payload.get("action", "").upper()
            data    = payload.get("data", {})

            def resolve_truck_names(items):
                resolve_errors = []
                try:
                    import ast
                    types_str = db.run("SELECT id, name FROM truck_type")
                    dcs_str = db.run("SELECT id, name FROM dc")
                    types_list = ast.literal_eval(types_str)
                    dcs_list = ast.literal_eval(dcs_str)
                    type_map = {str(name).lower(): tid for tid, name in types_list}
                    dc_map = {str(name).lower(): did for did, name in dcs_list}
                    
                    for idx, truck in enumerate(items):
                        if "type_id" not in truck and "type_name" in truck:
                            t_name = str(truck["type_name"]).lower()
                            if t_name in type_map:
                                truck["type_id"] = type_map[t_name]
                            else:
                                resolve_errors.append(f"Truk #{idx+1}: Tipe truk '{truck['type_name']}' tidak ditemukan. Opsi: {', '.join([n for _, n in types_list])}")
                        if "dc_id" not in truck and "dc_name" in truck:
                            d_name = str(truck["dc_name"]).lower()
                            if d_name in dc_map:
                                truck["dc_id"] = dc_map[d_name]
                            else:
                                resolve_errors.append(f"Truk #{idx+1}: DC '{truck['dc_name']}' tidak ditemukan. Opsi: {', '.join([n for _, n in dcs_list])}")
                except Exception as e:
                    pass
                return resolve_errors

            if action == "CREATE":
                if not isinstance(data, list) or len(data) == 0:
                    return {"ui_action": "ERROR", "message": "ERROR: For CREATE, 'data' must be a non-empty list of truck objects."}

                r_errors = resolve_truck_names(data)
                if r_errors:
                    return {"ui_action": "ERROR", "message": "ERROR: Gagal memproses data:\n" + "\n".join(r_errors)}

                required_fields = ["plate_number", "type_id", "dc_id", "max_individual_capacity_volume", "first_status"]
                validated_trucks = []
                errors = []

                for idx, truck in enumerate(data):
                    # Validasi field
                    missing = [f for f in required_fields if f not in truck]
                    if missing:
                        errors.append(f"Truk #{idx+1}: field wajib tidak lengkap ({', '.join(missing)})")
                        continue

                    # Validasi format plat
                    plate = truck.get("plate_number", "")
                    is_valid, error_msg = validate_plate_number(plate)
                    if not is_valid:
                        errors.append(f"Truk #{idx+1}: {error_msg}")
                        continue

                    truck["plate_number"] = plate.strip().upper()
                    if "first_status" not in truck:
                        truck["first_status"] = "AVAILABLE"
                    validated_trucks.append(truck)

                if errors:
                    return {"ui_action": "ERROR", "message": f"ERROR: Terdapat data tidak valid:\n" + "\n".join(errors)}

                return {
                    "ui_action": "PREFILL",
                    "target": "bulk_add_truck",
                    "data": validated_trucks,
                    "message": "Data truk telah disiapkan. Silakan periksa dan simpan di halaman review yang akan dibuka."
                }

            elif action == "UPDATE":
                if isinstance(data, dict):
                    data = [data]
                
                if not data:
                    return {"ui_action": "ERROR", "message": "ERROR: For UPDATE, 'data' must be a non-empty list of truck objects."}

                r_errors = resolve_truck_names(data)
                if r_errors:
                    return {"ui_action": "ERROR", "message": "ERROR: Gagal memproses data:\n" + "\n".join(r_errors)}

                validated_trucks = []
                errors = []

                for idx, truck in enumerate(data):
                    identifier = truck.get("plate_number") or truck.get("id")
                    if not identifier:
                        errors.append(f"Truk #{idx+1}: Missing plate_number or id for UPDATE.")
                        continue

                    ident_id = int(identifier) if str(identifier).isdigit() else 0

                    sql = text("SELECT id, plate_number, type_id, dc_id, max_individual_capacity_volume, first_status, second_status FROM truck WHERE plate_number = :ident OR id = :ident_id")
                    with db._engine.connect() as conn:
                        result = conn.execute(sql, {"ident": str(identifier), "ident_id": ident_id}).fetchone()
                        if not result:
                            errors.append(f"Truk #{idx+1}: Truk dengan plat/id {identifier} tidak ditemukan.")
                            continue
                        
                        db_id, db_plate, db_type, db_dc, db_vol, db_fs, db_ss = result
                        
                        merged_truck = {
                            "id": db_id,
                            "plate_number": truck.get("plate_number", db_plate),
                            "type_id": truck.get("type_id", db_type),
                            "dc_id": truck.get("dc_id", db_dc),
                            "max_individual_capacity_volume": truck.get("max_individual_capacity_volume", db_vol),
                            "first_status": truck.get("first_status") or truck.get("status") or db_fs,
                            "second_status": truck.get("second_status", db_ss)
                        }
                        validated_trucks.append(merged_truck)

                if errors:
                    return {"ui_action": "ERROR", "message": f"ERROR: Terdapat data tidak valid:\n" + "\n".join(errors)}

                return {
                    "ui_action": "PREFILL",
                    "target": "bulk_edit_truck",
                    "data": validated_trucks,
                    "message": "Data truk siap diedit."
                }

            elif action == "DELETE":
                identifier = data.get("plate_number") or data.get("id")
                if not identifier:
                    return {"ui_action": "ERROR", "message": "ERROR: Missing plate_number or id for DELETE."}

                where_clause = "plate_number = :ident" if data.get("plate_number") else "id = :ident"
                sql = text(f"DELETE FROM truck WHERE {where_clause}")
                with db._engine.connect() as conn:
                    conn.execute(sql, {"ident": identifier})
                    conn.commit()
                return {
                    "ui_action": "NAVIGATE",
                    "target": "trucks_list",
                    "message": f"Truk {identifier} berhasil dihapus."
                }

            return {"ui_action": "ERROR", "message": "ERROR: Invalid action."}
        except Exception as e:
            return {"ui_action": "ERROR", "message": f"ERROR: {str(e)}"}

    @tool
    def manage_location(query: dict | str) -> dict:
        """
        Use this tool for CREATE, UPDATE, or DELETE operations on location entities.
        Input must be a JSON string with:
        - action: 'CREATE', 'UPDATE', or 'DELETE'
        - data: dictionary of location fields.
        For CREATE: requires name, address, provinsi, kabupaten_kota, kecamatan, desa_kelurahan,
          kode_pos, open_hour, close_hour, customer_id, dc_id.
          Optional fields: latitude, longitude, service_time, is_dc.
          Note: Always use `get_available_options` first to find the correct `customer_id`
          and `dc_id` from names like "PT ABC" or "DC Jakarta".
        For UPDATE/DELETE: requires id.
        Example: {"action": "CREATE", "data": {"name": "Toko ABC", "address": "Jl. Merdeka 1", "provinsi": "DKI Jakarta", "kabupaten_kota": "Jakarta Pusat", "kecamatan": "Gambir", "desa_kelurahan": "Gambir", "kode_pos": "10110", "latitude": -6.123, "longitude": 106.123, "open_hour": "08:00", "close_hour": "17:00", "customer_id": 1, "dc_id": 1}}
        """
        try:
            payload = query if isinstance(query, dict) else json.loads(query)
            action  = payload.get("action", "").upper()
            data    = payload.get("data", {})

            if action == "CREATE":
                required = [
                    "name", "address", "provinsi", "kabupaten_kota", "kecamatan",
                    "desa_kelurahan", "kode_pos", "open_hour", "close_hour",
                    "customer_id", "dc_id",
                ]
                for field in required:
                    if field not in data:
                        return {"ui_action": "ERROR", "message": f"ERROR: Missing required field '{field}' for CREATE."}
                
                return {
                    "ui_action": "PREFILL",
                    "target": "add_location",
                    "data": data,
                    "message": "Data lokasi telah disiapkan. Silakan periksa dan simpan di form."
                }

            elif action == "UPDATE":
                location_id = data.get("id")
                if not location_id:
                    return {"ui_action": "ERROR", "message": "ERROR: Missing id for UPDATE."}
                
                prefill_data = {"Id": location_id, "prefill": data}
                return {
                    "ui_action": "PREFILL",
                    "target": "edit_location",
                    "data": prefill_data,
                    "message": "Data lokasi siap diedit."
                }

            elif action == "DELETE":
                identifier = data.get("id")
                if not identifier:
                    return {"ui_action": "ERROR", "message": "ERROR: Missing id for DELETE."}
                
                sql = text("DELETE FROM location WHERE id = :ident")
                with db._engine.connect() as conn:
                    conn.execute(sql, {"ident": identifier})
                    conn.commit()
                
                return {
                    "ui_action": "NAVIGATE",
                    "target": "locations_list",
                    "message": f"Lokasi dengan ID {identifier} berhasil dihapus."
                }

            return {"ui_action": "ERROR", "message": "ERROR: Invalid action."}
        except Exception as e:
            return {"ui_action": "ERROR", "message": f"ERROR: {str(e)}"}

    @tool
    def automate_shipment(
        optimization_type: str,
        start_date: str = None,
        end_date: str = None,
        customer_id: int = None,
        customer_name: str = None,
        kabupaten_kota: str = None,
        so_origin: str = None,
        delivery_order_num: str = None,
        delivery_order_ids: list[int] = None
    ) -> dict:
        """
        Use this tool to automatically create a shipment with optimization based on user request.
        Parameters:
        - optimization_type: 'distance' (for route optimization), 'emission' (for emissions), 'load' (for load optimization), or 'balance' (for distance and volume)
        - start_date: 'YYYY-MM-DD' (optional)
        - end_date: 'YYYY-MM-DD' (optional)
        - customer_id: integer (optional, ID of the customer from get_available_options)
        - customer_name: string (optional, Name of the customer)
        - kabupaten_kota: string (optional, City/District region name, e.g. 'Jakarta Selatan')
        - so_origin: string (optional, SO document origin/number, e.g. 'SO-001')
        - delivery_order_num: string (optional, DO document number, e.g. 'PRM/#DO-0019')
        - delivery_order_ids: list of integers (optional, specific delivery order IDs to include in the shipment, e.g. [5, 12, 20]). When provided, the system will use these exact IDs directly instead of querying by filters. Use this when the user specifies order IDs explicitly like 'buatkan shipment untuk order ID 5 dan 12'.
        """
        try:
            payload = {
                "optimization_type": optimization_type,
                "start_date": start_date,
                "end_date": end_date,
                "customer_id": customer_id,
                "customer_name": customer_name,
                "kabupaten_kota": kabupaten_kota,
                "so_origin": so_origin,
                "delivery_order_num": delivery_order_num,
                "delivery_order_ids": delivery_order_ids
            }
            # Remove None values
            payload = {k: v for k, v in payload.items() if v is not None}
            
            if not optimization_type:
                return {"ui_action": "ERROR", "message": "ERROR: Missing required field 'optimization_type' for automate_shipment."}
            
            if customer_name and not customer_id:
                try:
                    sql = text("SELECT id FROM customer WHERE name ILIKE :name AND is_deleted = false")
                    with db._engine.connect() as conn:
                        row = conn.execute(sql, {"name": f"%{customer_name}%"}).fetchone()
                    if row:
                        payload["customer_id"] = row[0]
                except Exception as e:
                    print(f"Error looking up customer in tools: {e}")

            payload["auto_submit"] = True
            return {
                "ui_action": "PREFILL",
                "target": "automate_shipment",
                "data": payload,
                "message": "Memulai proses pembuatan rute pengiriman otomatis berdasarkan kriteria Anda."
            }
        except Exception as e:
            return {"ui_action": "ERROR", "message": f"ERROR: {str(e)}"}


    @tool
    def manage_delivery_order(query: dict | str) -> dict:
        """
        Use this tool to CREATE a new delivery order.
        Input must be a JSON string with:
        - action: 'CREATE'
        - data: dictionary of delivery order fields.
        For CREATE: requires so_origin, delivery_order_num, eta_target, status, dc_id, customer_id.
          Optional: description, product_lines (list of products to load).
          - eta_target must be in ISO 8601 format: 'YYYY-MM-DDTHH:MM:SS' or 'YYYY-MM-DD'.
          - status must be one of: READY, PENDING, RUNNING, DONE, IN_CALCULATION.
          - dc_id: integer ID of the Distribution Center (use get_available_options to resolve from name).
          - customer_id: integer ID of the customer/tujuan (use get_available_options to resolve from name).
          - product_lines: optional list of products, each with fields:
              product_id (int), quantity (float), volume (float), weight (float), price (float)
              Use sql_db_query to find product IDs by name if user provides product names.
        ALWAYS call get_available_options FIRST to resolve dc_id and customer_id from names.
        IMPORTANT: This tool does NOT save to the database. It opens the create delivery order form with pre-filled data.
        Example:
          {"action": "CREATE", "data": {"so_origin": "SO-001", "delivery_order_num": "DO-001",
           "eta_target": "2026-06-13T08:00:00", "status": "READY", "dc_id": 1, "customer_id": 2,
           "product_lines": [{"product_id": 3, "quantity": 10, "volume": 5.0, "weight": 100.0, "price": 50000.0}]}}
        """
        try:
            payload = query if isinstance(query, dict) else json.loads(query)
            action  = payload.get("action", "").upper()
            data    = payload.get("data", {})

            if action == "CREATE":
                required = ["so_origin", "delivery_order_num", "eta_target", "status", "dc_id", "customer_id"]
                missing = [f for f in required if f not in data]
                if missing:
                    return {"ui_action": "ERROR", "message": f"ERROR: Field wajib tidak lengkap: {', '.join(missing)}. Mohon tanyakan ke pengguna."}

                valid_statuses = ["READY", "PENDING", "RUNNING", "DONE", "IN_CALCULATION"]
                if data.get("status", "").upper() not in valid_statuses:
                    return {"ui_action": "ERROR", "message": f"ERROR: Status '{data.get('status')}' tidak valid. Pilih salah satu dari: {', '.join(valid_statuses)}"}

                prefill_data = {
                    "so_origin": data["so_origin"],
                    "delivery_order_num": data["delivery_order_num"],
                    "eta_target": data["eta_target"],
                    "status": data["status"].upper(),
                    "dc_id": int(data["dc_id"]),
                    "customer_id": int(data["customer_id"]),
                }
                if "description" in data:
                    prefill_data["description"] = data["description"]
                if "product_lines" in data and isinstance(data["product_lines"], list):
                    prefill_data["product_lines"] = [
                        {
                            "product_id": int(pl.get("product_id", 0)),
                            "quantity": float(pl.get("quantity", 1)),
                            "volume": float(pl.get("volume", 0)),
                            "weight": float(pl.get("weight", 0)),
                            "price": float(pl.get("price", 0)),
                        }
                        for pl in data["product_lines"]
                    ]

                return {
                    "ui_action": "PREFILL",
                    "target": "create_delivery_order",
                    "data": prefill_data,
                    "message": "Data delivery order telah disiapkan. Silakan periksa dan simpan di form yang akan dibuka."
                }

            return {"ui_action": "ERROR", "message": "ERROR: Action tidak dikenal. Gunakan 'CREATE'."}
        except Exception as e:
            return {"ui_action": "ERROR", "message": f"ERROR: {str(e)}"}

    @tool
    def simulate_shipment(
        optimization_type: str,
        delivery_order_ids: list[int] = None,
        start_date: str = None,
        end_date: str = None,
        customer_id: int = None,
        kabupaten_kota: str = None,
    ) -> str:
        """
        Use this tool to SIMULATE (dry-run/preview) route optimization WITHOUT saving anything to the database.
        Use this when the user asks things like:
        - "Kira-kira kalau...", "Simulasikan...", "Cek dulu berapa truk yang dibutuhkan...",
          "Estimasi rute untuk...", "Berapa total jarak kalau...", "Tes dulu..."
        This tool calls the same optimization algorithm as automate_shipment, but results are NOT saved.
        Returns a human-readable summary of the estimated shipment plan.
        Parameters:
        - optimization_type: 'distance', 'emission', 'load', or 'balance'
        - delivery_order_ids: list of specific delivery order IDs (optional)
        - start_date: 'YYYY-MM-DD' (optional)
        - end_date: 'YYYY-MM-DD' (optional)
        - customer_id: integer customer ID (optional)
        - kabupaten_kota: city/district filter (optional)
        """
        try:
            from context import request_token
            _gateway_url = os.getenv("REACT_APP_BACKEND_URL", "http://localhost:8080")
            _gateway_token = request_token.get() or os.getenv("API_GATEWAY_SIMULATE_TOKEN", "")

            payload = {"priority": optimization_type}
            if delivery_order_ids:
                payload["delivery_orders_id"] = delivery_order_ids
            if start_date:
                payload["start_date"] = start_date
            if end_date:
                payload["end_date"] = end_date
            if customer_id:
                payload["customer_id"] = customer_id
            if kabupaten_kota:
                payload["kabupaten_kota"] = kabupaten_kota

            headers = {"Content-Type": "application/json"}
            if _gateway_token:
                headers["Authorization"] = f"Bearer {_gateway_token}"

            resp = http_requests.post(
                f"{_gateway_url}/api/v1/priority-opt?preview=true",
                json=payload,
                headers=headers,
                timeout=120,
            )

            if resp.status_code != 200:
                return f"Simulasi gagal: server mengembalikan status {resp.status_code}. Pesan: {resp.text[:300]}"

            result = resp.json()
            data = result.get("data", result)
            shipments = data.get("shipments", [])
            failed_dos = data.get("failed_delivery_orders", [])

            if not shipments:
                total_failed = len(failed_dos)
                return (
                    f"Hasil simulasi: Tidak ada rute yang dapat dibentuk dari pesanan yang diberikan.\n"
                    f"Total pesanan yang tidak bisa dijadwalkan: {total_failed}"
                )

            lines = [f"**Hasil Simulasi Rute ({optimization_type.upper()})**\n"]
            total_orders = 0
            total_dist_m = 0
            total_time_min = 0

            for i, s in enumerate(shipments, 1):
                truck = s.get("truck", {})
                truck_plate = truck.get("plate_number", "N/A")
                truck_type = truck.get("truck_type", {}).get("name", "N/A") if isinstance(truck.get("truck_type"), dict) else "N/A"
                dos = s.get("delivery_orders", [])
                dist_m = s.get("total_dist", 0) or 0
                time_min = s.get("total_time", 0) or 0
                curr_cap = s.get("current_capacity", 0) or 0
                max_cap = s.get("max_capacity", 1) or 1
                emission = s.get("total_emission")

                total_orders += len(dos)
                total_dist_m += dist_m
                total_time_min += time_min

                dist_km = dist_m / 1000
                time_h = int(time_min // 60)
                time_m = int(time_min % 60)
                fill_pct = round((curr_cap / max_cap) * 100, 1) if max_cap else 0

                truck_line = f"Truk {i}: {truck_plate} ({truck_type})"
                details = [
                    f"  • Pesanan: {len(dos)} DO",
                    f"  • Jarak: {dist_km:.2f} km",
                    f"  • Est. Waktu: {time_h}j {time_m}m",
                    f"  • Muatan: {fill_pct}% dari kapasitas",
                ]
                if emission is not None:
                    details.append(f"  • Emisi CO₂: {emission/1000:.2f} kg")

                lines.append(truck_line)
                lines.extend(details)
                lines.append("")

            summary = [
                f"**Ringkasan Simulasi:**",
                f"  - Total truk digunakan : {len(shipments)} truk",
                f"  - Total pesanan terlayani: {total_orders} DO",
                f"  - Total jarak keseluruhan: {total_dist_m/1000:.2f} km",
                f"  - Pesanan tidak terjadwalkan: {len(failed_dos)} DO",
                f"",
                f"Ini hanya simulasi. Data belum disimpan ke sistem.",
                f"Jika Anda puas dengan hasilnya, katakan 'buat pengiriman' untuk memproses secara resmi.",
            ]
            lines.extend(summary)

            return "\n".join(lines)

        except http_requests.exceptions.ConnectionError:
            return "Simulasi gagal: tidak dapat terhubung ke server optimasi. Pastikan API Gateway berjalan."
        except http_requests.exceptions.Timeout:
            return "Simulasi gagal: server optimasi membutuhkan waktu terlalu lama (timeout). Coba kurangi jumlah pesanan."
        except Exception as e:
            return f"Simulasi gagal karena kesalahan tak terduga: {str(e)}"

    return [system_control, get_available_options, manage_truck, manage_location, automate_shipment, simulate_shipment, manage_delivery_order]
