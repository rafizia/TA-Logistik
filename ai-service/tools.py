import re
import json
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
    def system_control(action_type: str = "NAVIGATE", target_page: str = "dashboard") -> dict:
        """
        VERY IMPORTANT: Use this tool for navigation or system actions.
        """
        try:
            return {
                "ui_action": action_type,
                "target": target_page,
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
        For CREATE: data must be a LIST of truck objects. Requires plate_number, type_id, dc_id, max_individual_capacity_volume, first_status
          Use this when user wants to create one or more trucks.
          IMPORTANT: plate_number MUST follow Indonesian license plate format:
          [1-2 letter area code] [1-4 digit registration number] [1-3 letter series code]
          Each part separated by a SINGLE SPACE. Example: "B 1234 RFS", "AB 12 CD".
          Example: {"action": "CREATE", "data": [{"plate_number": "B 1234 AB", "type_id": 1, "dc_id": 1, "max_individual_capacity_volume": 1500000, "first_status": "AVAILABLE"}, {"plate_number": "B 5678 CD", "type_id": 1, "dc_id": 1, "max_individual_capacity_volume": 1000000, "first_status": "AVAILABLE"}]}
        For UPDATE/DELETE: requires plate_number or id.
        """
        try:
            payload = query if isinstance(query, dict) else json.loads(query)
            action  = payload.get("action", "").upper()
            data    = payload.get("data", {})

            if action == "CREATE":
                if not isinstance(data, list) or len(data) == 0:
                    return {"ui_action": "ERROR", "message": "ERROR: For CREATE, 'data' must be a non-empty list of truck objects."}

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

    return [system_control, get_available_options, manage_truck, manage_location, automate_shipment]
