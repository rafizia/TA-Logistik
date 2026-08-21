import ast
from typing import Optional, Literal
from pydantic import BaseModel, Field
from langchain.tools import tool


CREATE_REQUIRED_LOCATION_FIELDS = [
    "name", "address", "provinsi", "kabupaten_kota", "kecamatan",
    "desa_kelurahan", "kode_pos", "customer_id", "dc_id",
]


class LocationItemInput(BaseModel):
    id: Optional[str] = Field(
        default=None,
        description="Location UUID string (required for UPDATE). Must be the exact UUID from the database."
    )
    name: Optional[str] = Field(
        default=None,
        description="Location name (example: 'Toko ABC')."
    )
    latitude: Optional[float] = Field(
        default=None,
        description="Latitude coordinate (example: -6.1234)."
    )
    longitude: Optional[float] = Field(
        default=None,
        description="Longitude coordinate (example: 106.1234)."
    )
    address: Optional[str] = Field(
        default=None,
        description="Full address of the location (example: 'Jl. ABC No. 123')."
    )
    provinsi: Optional[str] = Field(
        default=None,
        description="Province name (example: 'DKI Jakarta')."
    )
    kabupaten_kota: Optional[str] = Field(
        default=None,
        description="City/Regency name (example: 'Jakarta Pusat')."
    )
    kecamatan: Optional[str] = Field(
        default=None,
        description="District name (example: 'Gambir')."
    )
    desa_kelurahan: Optional[str] = Field(
        default=None,
        description="Village/Urban Village name (example: 'Gambir')."
    )
    kode_pos: Optional[str] = Field(
        default=None,
        description="Postal code (example: '10110')."
    )
    open_hour: Optional[str] = Field(
        default=None,
        description="Opening hour of the location (example: '08:00')."
    )
    close_hour: Optional[str] = Field(
        default=None,
        description="Closing hour of the location (example: '17:00')."
    )
    service_time: Optional[int] = Field(
        default=None,
        description="Service time in minutes (example: 15)."
    )
    customer_id: Optional[int] = Field(
        default=None,
        description="Customer numeric ID. Can be replaced with customer_name."
    )
    customer_name: Optional[str] = Field(
        default=None,
        description="Customer name (example: 'PT ABC')."
    )
    dc_id: Optional[int] = Field(
        default=None,
        description="Distribution Center numeric ID. Can be replaced with dc_name."
    )
    dc_name: Optional[str] = Field(
        default=None,
        description="Distribution Center name (example: 'DC Jakarta')."
    )
    is_dc: Optional[bool] = Field(
        default=False,
        description="Whether the location is a Distribution Center."
    )


class ManageLocationInput(BaseModel):
    action: Literal["CREATE", "UPDATE"] = Field(
        description="Action to be performed on the location entity: 'CREATE' or 'UPDATE'."
    )
    data: LocationItemInput = Field(
        description="Location data object to be created or updated."
    )


def _resolve_location_names_to_ids(location_data: dict, db) -> list[str]:
    """Resolve customer_name -> customer_id and dc_name -> dc_id in-place."""
    errors: list[str] = []
    try:
        if not location_data.get("customer_id") and location_data.get("customer_name"):
            customers_str = db.run("SELECT id, name FROM customer")
            customers_list: list[tuple] = ast.literal_eval(customers_str)
            cust_map = {str(name).lower(): cid for cid, name in customers_list}
            key = str(location_data["customer_name"]).lower()
            if key in cust_map:
                location_data["customer_id"] = cust_map[key]
            else:
                options = ", ".join(name for _, name in customers_list)
                errors.append(f"Customer '{location_data['customer_name']}' not found. Options: {options}")

        if not location_data.get("dc_id") and location_data.get("dc_name"):
            dcs_str = db.run("SELECT id, name FROM dc")
            dcs_list: list[tuple] = ast.literal_eval(dcs_str)
            dc_map = {str(name).lower(): did for did, name in dcs_list}
            key = str(location_data["dc_name"]).lower()
            if key in dc_map:
                location_data["dc_id"] = dc_map[key]
            else:
                options = ", ".join(name for _, name in dcs_list)
                errors.append(f"DC '{location_data['dc_name']}' not found. Options: {options}")
    except Exception:
        pass
    return errors

def _error(msg: str) -> dict:
    return {"status": "error", "ui_action": "ERROR", "message": msg}

def _success(ui_action: str, target: str, data, message: str) -> dict:
    return {"status": "success", "ui_action": ui_action, "target": target, "data": data, "message": message}

def get_manage_location_tool(db):
    @tool(args_schema=ManageLocationInput)
    def manage_location(action: str, data: LocationItemInput) -> dict:
        """
        Use this tool for CREATE or UPDATE operations on location entities.
        - action: 'CREATE' or 'UPDATE'
        - data: Location object containing fields like name, address, provinsi, kabupaten_kota,
          kecamatan, desa_kelurahan, kode_pos, open_hour, close_hour, customer_name/customer_id, dc_name/dc_id.
        """
        try:
            loc_dict: dict = data.model_dump(exclude_unset=True) if isinstance(data, BaseModel) else dict(data)
            action_upper = action.upper()

            resolve_errors = _resolve_location_names_to_ids(loc_dict, db)
            if resolve_errors:
                return _error("Error resolving location names:\n" + "\n".join(resolve_errors))

            if action_upper == "CREATE":
                missing = [f for f in CREATE_REQUIRED_LOCATION_FIELDS if loc_dict.get(f) is None]
                if missing:
                    return _error(f"Missing required fields for CREATE: {', '.join(missing)}.")

                return _success(
                    "PREFILL", "add_location", loc_dict,
                    "Data lokasi siap. Silakan periksa dan simpan di form."
                )

            elif action_upper == "UPDATE":
                location_id = loc_dict.get("id")
                if not location_id:
                    return _error("Missing required field 'id' for UPDATE location.")

                prefill = {
                    k: v for k, v in loc_dict.items()
                    if k not in {"id", "dc_name", "customer_name", "customer_id"}
                }
                prefill_data = {"Id": location_id, "prefill": prefill}
                return _success(
                    "PREFILL", "edit_location", prefill_data,
                    "Data lokasi siap diedit."
                )

            return _error("Action not known. Use 'CREATE' or 'UPDATE'.")
        except Exception as e:
            return _error(f"Unexpected error: {str(e)}")

    return manage_location
