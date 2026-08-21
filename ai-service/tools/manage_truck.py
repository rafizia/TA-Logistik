import ast
import re
from typing import Optional, List, Literal
from langchain.tools import tool
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import text


PLATE_NUMBER_REGEX = re.compile(
    r'^[A-Z]{1,2}\s[0-9]{1,4}\s[A-Z]{1,3}$',
    re.IGNORECASE
)
CREATE_REQUIRED_FIELDS = ["plate_number", "type_id", "dc_id", "max_individual_capacity_volume"]

UPDATE_ALLOWED_FIELDS: set[str] = {"dc_id", "dc_name", "first_status", "second_status"}

TruckFirstStatus  = Literal["AVAILABLE", "UNAVAILABLE"]
TruckSecondStatus = Literal["ON_DELIVERY", "OUT_OF_STOCK", "ARCHIVE", "MAINTENANCE", "LEGAL"]


class TruckItemInput(BaseModel):
    id: Optional[int] = Field(
        default=None,
        description="Numeric truck ID (used for UPDATE if plate_number is not available)."
    )
    plate_number: Optional[str] = Field(
        default=None,
        description="Indonesian truck license plate (example: 'B 1234 AB')."
    )
    type_id: Optional[int] = Field(
        default=None,
        description="Vehicle type ID. Can be replaced with type_name."
    )
    type_name: Optional[str] = Field(
        default=None,
        description="Vehicle type name (example: 'Blind Van', 'CDD', 'CDE')."
    )
    dc_id: Optional[int] = Field(
        default=None,
        description="Distribution Center ID. Can be replaced with dc_name."
    )
    dc_name: Optional[str] = Field(
        default=None,
        description="Distribution Center name (example: 'DC Jakarta')."
    )
    max_individual_capacity_volume: Optional[float] = Field(
        default=None,
        description="Maximum truck volume capacity (in cm³)."
    )
    first_status: Optional[TruckFirstStatus] = Field(
        default="AVAILABLE",
        description="Primary truck status: 'AVAILABLE' or 'UNAVAILABLE'."
    )
    second_status: Optional[TruckSecondStatus] = Field(
        default=None,
        description="Secondary truck status: 'ON_DELIVERY', 'MAINTENANCE', etc."
    )

    @field_validator("plate_number")
    @classmethod
    def check_plate_format(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            v_stripped = v.strip().upper()
            if not PLATE_NUMBER_REGEX.match(v_stripped):
                raise ValueError(
                    f"Plate number format '{v}' is not valid. "
                    f"Must follow Indonesian format (example: 'B 1234 AB')."
                )
            return v_stripped
        return v

class ManageTruckInput(BaseModel):
    action: Literal["CREATE", "UPDATE"] = Field(
        description="Action to perform: 'CREATE' or 'UPDATE'."
    )
    data: List[TruckItemInput] = Field(
        description="List of trucks to be created or updated (minimum 1 item)."
    )

    @model_validator(mode="after")
    def validate_data_not_empty(self):
        if not self.data:
            raise ValueError("Parameter 'data' cannot be empty. Please provide at least 1 truck data.")
        return self


def _resolve_names_to_ids(truck_list: list[dict], db) -> list[str]:
    """Resolve type_name -> type_id and dc_name -> dc_id."""
    resolve_errors = []
 
    try:
        types_str = db.run("SELECT id, name FROM truck_type")
        dcs_str = db.run("SELECT id, name FROM dc")
    except Exception as e:
        return [f"Failed to retrieve reference data from database: {str(e)}"]
 
    try:
        types_list = ast.literal_eval(types_str)
        dcs_list = ast.literal_eval(dcs_str)
    except (ValueError, SyntaxError) as e:
        return [f"Failed to parse reference data: {str(e)}"]
 
    type_map = {str(name).lower(): tid for tid, name in types_list}
    dc_map = {str(name).lower(): did for did, name in dcs_list}
 
    for idx, truck in enumerate(truck_list):
        if not truck.get("type_id") and truck.get("type_name"):
            t_name = str(truck["type_name"]).lower()
            if t_name in type_map:
                truck["type_id"] = type_map[t_name]
            else:
                resolve_errors.append(
                    f"Truck #{idx+1}: Truck type '{truck['type_name']}' not found. "
                    f"Options: {', '.join(n for _, n in types_list)}"
                )
        if not truck.get("dc_id") and truck.get("dc_name"):
            d_name = str(truck["dc_name"]).lower()
            if d_name in dc_map:
                truck["dc_id"] = dc_map[d_name]
            else:
                resolve_errors.append(
                    f"Truck #{idx+1}: DC '{truck['dc_name']}' not found. "
                    f"Options: {', '.join(n for _, n in dcs_list)}"
                )
 
    return resolve_errors

def _error(msg: str) -> dict:
    return {"status": "error", "ui_action": "ERROR", "message": msg}

def _success_prefill(target: str, data, message: str) -> dict:
    return {"status": "success", "ui_action": "PREFILL", "target": target, "data": data, "message": message}

def get_manage_truck_tool(db):
    @tool(args_schema=ManageTruckInput)
    def manage_truck(action: str, data: List[TruckItemInput]) -> dict:
        """
        Use this tool to CREATE or UPDATE truck data.
        - action: 'CREATE' or 'UPDATE'
        - data: list of truck objects; each item can use type_name/dc_name
          as an alternative to type_id/dc_id.
        This tool does not save directly to the database — the result is sent
        to the UI form page for user confirmation.
        """
        try:
            items: list[dict] = [
                item.model_dump(exclude_unset=True) if isinstance(item, BaseModel) else dict(item)
                for item in data
            ]
            resolve_errors = _resolve_names_to_ids(items, db)
            if resolve_errors:
                return _error("Failed to process data:\n" + "\n".join(resolve_errors))

            if action.upper() == "CREATE":
                return _handle_create(items)
            else:
                return _handle_update(items, db)

        except Exception as e:
            return _error(f"Unexpected error: {e}")

    def _handle_create(items: list[dict]) -> dict:
        validated, errors = [], []
        for idx, truck in enumerate(items):
            label = f"Truck #{idx + 1}"
            missing = [f for f in CREATE_REQUIRED_FIELDS if not truck.get(f)]
            if missing:
                errors.append(f"{label}: missing required field ({', '.join(missing)})")
                continue
            truck["plate_number"] = truck["plate_number"].strip().upper()
            truck.setdefault("first_status", "AVAILABLE")
            validated.append(truck)

        if errors:
            return _error("Invalid data:\n" + "\n".join(errors))

        return _success_prefill(
            "bulk_add_truck", validated,
            "Data truk telah siap. Silahkan cek dan simpan di halaman review."
        )

    def _handle_update(items: list[dict], db) -> dict:
        validated, errors = [], []
        sql = text(
            "SELECT id, plate_number, type_id, dc_id, "
            "max_individual_capacity_volume, first_status, second_status "
            "FROM truck WHERE plate_number = :plate OR id = :id"
        )
        for idx, truck in enumerate(items):
            label = f"Truck #{idx + 1}"
            identifier = truck.get("plate_number") or truck.get("id")
            if not identifier:
                errors.append(f"{label}: plate_number or id is required for UPDATE.")
                continue

            # Reject fields that are not in the allowed update whitelist
            changed_fields = set(truck.keys()) - {"plate_number", "id"}
            forbidden = changed_fields - UPDATE_ALLOWED_FIELDS
            if forbidden:
                readable_allowed = ", ".join(sorted(UPDATE_ALLOWED_FIELDS))
                errors.append(
                    f"{label}: field(s) not allowed to be updated: {', '.join(sorted(forbidden))}. "
                    f"Only the following fields may be changed: {readable_allowed}."
                )
                continue

            ident_id = int(identifier) if str(identifier).isdigit() else 0
            with db._engine.connect() as conn:
                row = conn.execute(sql, {"plate": str(identifier), "id": ident_id}).fetchone()

            if not row:
                errors.append(f"{label}: truck with plate/id '{identifier}' not found.")
                continue

            db_id, db_plate, db_type, db_dc, db_vol, db_fs, db_ss = row
            validated.append({
                "id":          db_id,
                "plate_number": db_plate,
                "type_id":     db_type,
                "dc_id":       truck.get("dc_id", db_dc),
                "max_individual_capacity_volume": db_vol,
                "first_status":  truck.get("first_status") or db_fs,
                "second_status": truck.get("second_status", db_ss),
            })

        if errors:
            return _error("Invalid data:\n" + "\n".join(errors))

        return _success_prefill(
            "bulk_edit_truck", validated,
            "Data truk telah siap untuk diedit."
        )

    return manage_truck
