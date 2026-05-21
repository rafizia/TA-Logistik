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
    def system_control(query: str) -> str:
        """
        VERY IMPORTANT: Use this tool for navigation or system actions.
        The Action Input MUST be a valid JSON string with 'action_type' and 'target_page'.
        Example Action Input: {"action_type": "NAVIGATE", "target_page": "trucks_list"}
        """
        try:
            data = json.loads(query)
            action_type = data.get("action_type", "NAVIGATE")
            target_page = data.get("target_page", "dashboard")
            return f"SUCCESS:{action_type}:{target_page}"
        except Exception:
            return f"SUCCESS:NAVIGATE:{query}"

    @tool
    def get_available_options(query: str = "") -> str:
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
    def manage_truck(query: str) -> str:
        """
        Use this tool for CREATE, UPDATE, or DELETE operations on truck entities.
        Input must be a JSON string with:
        - action: 'CREATE', 'UPDATE', or 'DELETE'
        - data: dictionary of truck fields.
        For CREATE: requires plate_number, type_id, dc_id, first_status, created_by.
          Optional: max_individual_capacity_volume.
          IMPORTANT: plate_number MUST follow Indonesian license plate format:
          [1-2 letter area code] [1-4 digit registration number] [1-3 letter series code]
          Each part separated by a SINGLE SPACE. Example: "B 1234 RFS", "AB 12 CD".
        For UPDATE/DELETE: requires plate_number or id.
        Example: {"action": "CREATE", "data": {"plate_number": "B 1234 XY", "type_id": 1, "dc_id": 1, "first_status": "AVAILABLE", "created_by": "AI_Agent", "max_individual_capacity_volume": 150000}}
        """
        try:
            payload = json.loads(query)
            action  = payload.get("action").upper()
            data    = payload.get("data", {})

            if action == "CREATE":
                # Validasi field wajib
                required = ["plate_number", "type_id", "dc_id", "first_status"]
                for field in required:
                    if field not in data:
                        return f"ERROR: Missing required field '{field}' for CREATE."

                # Validasi format plat nomor Indonesia
                plate = data.get("plate_number", "")
                is_valid, error_msg = validate_plate_number(plate)
                if not is_valid:
                    return f"ERROR: {error_msg}"

                # Normalisasi: uppercase
                data["plate_number"] = plate.strip().upper()
                return f"SUCCESS:PREFILL:add_truck:{json.dumps(data)}"

            elif action == "UPDATE":
                identifier = data.get("plate_number") or data.get("id")
                if not identifier:
                    return "ERROR: Missing plate_number or id for UPDATE."

                truck_id = data.get("id")
                if not truck_id:
                    sql = text("SELECT id FROM truck WHERE plate_number = :plate")
                    with db._engine.connect() as conn:
                        result = conn.execute(sql, {"plate": identifier}).fetchone()
                        if not result:
                            return f"ERROR: Truck with plate {identifier} not found."
                        truck_id = result[0]

                prefill_data = {
                    "Id": truck_id,
                    "prefill": {
                        "dc_id": data.get("dc_id"),
                        "status": (
                            data.get("status") or data.get("first_status") or
                            data.get("second_status") or data.get("third_status")
                        ),
                    },
                }
                return f"SUCCESS:PREFILL:edit_truck:{json.dumps(prefill_data)}"

            elif action == "DELETE":
                identifier = data.get("plate_number") or data.get("id")
                if not identifier:
                    return "ERROR: Missing plate_number or id for DELETE."

                where_clause = "plate_number = :ident" if data.get("plate_number") else "id = :ident"
                sql = text(f"DELETE FROM truck WHERE {where_clause}")
                with db._engine.connect() as conn:
                    conn.execute(sql, {"ident": identifier})
                    conn.commit()
                return f"SUCCESS: Truck {identifier} deleted successfully."

            return "ERROR: Invalid action."
        except Exception as e:
            return f"ERROR: {str(e)}"

    @tool
    def manage_location(query: str) -> str:
        """
        Use this tool for CREATE, UPDATE, or DELETE operations on location entities.
        Input must be a JSON string with:
        - action: 'CREATE', 'UPDATE', or 'DELETE'
        - data: dictionary of location fields.
        For CREATE: requires address, provinsi, kabupaten_kota, kecamatan, desa_kelurahan,
          kode_pos, open_hour, close_hour, customer_id, dc_id.
          Note: Always use `get_available_options` first to find the correct `customer_id`
          and `dc_id` from names like "PT ABC" or "DC Jakarta".
        For UPDATE/DELETE: requires id.
        Example: {"action": "CREATE", "data": {"address": "Jl. Merdeka 1", "provinsi": "DKI Jakarta", "kabupaten_kota": "Jakarta Pusat", "kecamatan": "Gambir", "desa_kelurahan": "Gambir", "kode_pos": "10110", "open_hour": "08:00", "close_hour": "17:00", "customer_id": 1, "dc_id": 1}}
        """
        try:
            payload = json.loads(query)
            action  = payload.get("action").upper()
            data    = payload.get("data", {})

            if action == "CREATE":
                required = [
                    "address", "provinsi", "kabupaten_kota", "kecamatan",
                    "desa_kelurahan", "kode_pos", "open_hour", "close_hour",
                    "customer_id", "dc_id",
                ]
                for field in required:
                    if field not in data:
                        return f"ERROR: Missing required field '{field}' for CREATE."
                return f"SUCCESS:PREFILL:add_location:{json.dumps(data)}"

            elif action == "UPDATE":
                location_id = data.get("id")
                if not location_id:
                    return "ERROR: Missing id for UPDATE."
                prefill_data = {"Id": location_id, "prefill": data}
                return f"SUCCESS:PREFILL:edit_location:{json.dumps(prefill_data)}"

            elif action == "DELETE":
                identifier = data.get("id")
                if not identifier:
                    return "ERROR: Missing id for DELETE."
                sql = text("DELETE FROM location WHERE id = :ident")
                with db._engine.connect() as conn:
                    conn.execute(sql, {"ident": identifier})
                    conn.commit()
                return f"SUCCESS: Location {identifier} deleted successfully."

            return "ERROR: Invalid action."
        except Exception as e:
            return f"ERROR: {str(e)}"

    return [system_control, get_available_options, manage_truck, manage_location]
