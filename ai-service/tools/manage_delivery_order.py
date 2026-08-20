import ast
from typing import Optional, List, Literal
from pydantic import BaseModel, Field
from langchain.tools import tool
from sqlalchemy import text

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DeliveryOrderStatus = Literal["READY", "PENDING", "RUNNING", "DONE", "IN_CALCULATION"]
CREATE_REQUIRED_DO_FIELDS = ["so_origin", "delivery_order_num", "eta_target", "status", "dc_id", "customer_id"]

# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class DeliveryOrderProductLineInput(BaseModel):
    product_id: Optional[int] = Field(
        default=None,
        description="ID numerik produk (dapat digantikan dengan product_name)."
    )
    product_name: Optional[str] = Field(
        default=None,
        description="Nama produk (contoh: 'Produk A')."
    )
    quantity: Optional[float] = Field(
        default=1.0,
        description="Jumlah kuantitas produk."
    )
    volume: Optional[float] = Field(
        default=0.0,
        description="Volume total produk."
    )
    weight: Optional[float] = Field(
        default=0.0,
        description="Berat total produk."
    )
    price: Optional[float] = Field(
        default=0.0,
        description="Harga total produk."
    )


class DeliveryOrderItemInput(BaseModel):
    id: Optional[int] = Field(
        default=None,
        description="ID numerik delivery order (wajib untuk UPDATE jika delivery_order_num tidak diberikan)."
    )
    so_origin: Optional[str] = Field(
        default=None,
        description="Nomor Sales Order asal (contoh: 'SO-001')."
    )
    delivery_order_num: Optional[str] = Field(
        default=None,
        description="Nomor Delivery Order (contoh: 'DO-001')."
    )
    eta_target: Optional[str] = Field(
        default=None,
        description="Target waktu kedatangan dalam format ISO 8601 (contoh: '2026-06-13T08:00:00' atau '2026-06-13')."
    )
    status: Optional[DeliveryOrderStatus] = Field(
        default=None,
        description="Status delivery order: 'READY', 'PENDING', 'RUNNING', 'DONE', atau 'IN_CALCULATION'."
    )
    dc_id: Optional[int] = Field(
        default=None,
        description="ID Distribution Center. Bisa digantikan dengan dc_name."
    )
    dc_name: Optional[str] = Field(
        default=None,
        description="Nama Distribution Center (contoh: 'DC Jakarta')."
    )
    customer_id: Optional[int] = Field(
        default=None,
        description="ID customer penerima. Bisa digantikan dengan customer_name."
    )
    customer_name: Optional[str] = Field(
        default=None,
        description="Nama customer penerima (contoh: 'PT ABC')."
    )
    description: Optional[str] = Field(
        default=None,
        description="Deskripsi atau catatan tambahan."
    )
    product_lines: Optional[List[DeliveryOrderProductLineInput]] = Field(
        default=None,
        description="Daftar produk yang dimuat dalam delivery order ini."
    )


class ManageDeliveryOrderInput(BaseModel):
    action: Literal["CREATE", "UPDATE"] = Field(
        description="Tindakan yang akan dilakukan pada delivery order: 'CREATE' atau 'UPDATE'."
    )
    data: DeliveryOrderItemInput = Field(
        description="Objek data delivery order yang akan dibuat atau diperbarui."
    )

# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def _resolve_do_names_to_ids(do_data: dict, db) -> list[str]:
    """
    Resolve customer_name → customer_id, dc_name → dc_id, dan product_name → product_id secara in-place.
    """
    errors: list[str] = []
    try:
        if not do_data.get("customer_id") and do_data.get("customer_name"):
            customers_str = db.run("SELECT id, name FROM customer")
            customers_list: list[tuple] = ast.literal_eval(customers_str)
            cust_map = {str(name).lower(): cid for cid, name in customers_list}
            key = str(do_data["customer_name"]).lower()
            if key in cust_map:
                do_data["customer_id"] = cust_map[key]
            else:
                options = ", ".join(name for _, name in customers_list)
                errors.append(f"Customer '{do_data['customer_name']}' tidak ditemukan. Opsi: {options}")

        if not do_data.get("dc_id") and do_data.get("dc_name"):
            dcs_str = db.run("SELECT id, name FROM dc")
            dcs_list: list[tuple] = ast.literal_eval(dcs_str)
            dc_map = {str(name).lower(): did for did, name in dcs_list}
            key = str(do_data["dc_name"]).lower()
            if key in dc_map:
                do_data["dc_id"] = dc_map[key]
            else:
                options = ", ".join(name for _, name in dcs_list)
                errors.append(f"DC '{do_data['dc_name']}' tidak ditemukan. Opsi: {options}")

        if "product_lines" in do_data and isinstance(do_data["product_lines"], list):
            products_str = db.run("SELECT id, name FROM product")
            products_list: list[tuple] = ast.literal_eval(products_str)
            prod_map = {str(name).lower(): pid for pid, name in products_list}
            for idx, pl in enumerate(do_data["product_lines"]):
                if isinstance(pl, dict) and not pl.get("product_id") and pl.get("product_name"):
                    key = str(pl["product_name"]).lower()
                    if key in prod_map:
                        pl["product_id"] = prod_map[key]
                    else:
                        options = ", ".join(name for _, name in products_list)
                        errors.append(f"Produk #{idx+1} ('{pl['product_name']}') tidak ditemukan. Opsi: {options}")
    except Exception:
        pass
    return errors


def _error(msg: str) -> dict:
    return {"status": "error", "ui_action": "ERROR", "message": msg}


def _success(ui_action: str, target: str, data, message: str) -> dict:
    return {"status": "success", "ui_action": ui_action, "target": target, "data": data, "message": message}

# ---------------------------------------------------------------------------
# Tool Factory
# ---------------------------------------------------------------------------

def get_manage_delivery_order_tool(db):
    """Factory — mengembalikan tool manage_delivery_order yang terikat ke DB."""

    @tool(args_schema=ManageDeliveryOrderInput)
    def manage_delivery_order(action: str, data: DeliveryOrderItemInput) -> dict:
        """
        Use this tool to CREATE or UPDATE a delivery order.
        - action: 'CREATE' or 'UPDATE'
        - data: delivery order object containing fields like so_origin, delivery_order_num, eta_target, status, customer_name/customer_id, dc_name/dc_id, product_lines.
        """
        try:
            do_dict: dict = data.model_dump(exclude_unset=True) if isinstance(data, BaseModel) else dict(data)
            action_upper = action.upper()

            resolve_errors = _resolve_do_names_to_ids(do_dict, db)
            if resolve_errors:
                return _error("Gagal memproses data delivery order:\n" + "\n".join(resolve_errors))

            if action_upper == "CREATE":
                missing = [f for f in CREATE_REQUIRED_DO_FIELDS if do_dict.get(f) is None]
                if missing:
                    return _error(f"Field wajib tidak lengkap untuk CREATE: {', '.join(missing)}.")

                prefill_data = {
                    "so_origin": do_dict["so_origin"],
                    "delivery_order_num": do_dict["delivery_order_num"],
                    "eta_target": do_dict["eta_target"],
                    "status": str(do_dict["status"]).upper(),
                    "dc_id": int(do_dict["dc_id"]),
                    "customer_id": int(do_dict["customer_id"]),
                }
                if "description" in do_dict and do_dict["description"]:
                    prefill_data["description"] = do_dict["description"]
                if "product_lines" in do_dict and isinstance(do_dict["product_lines"], list):
                    prefill_data["product_lines"] = [
                        {
                            "product_id": int(pl.get("product_id", 0)),
                            "quantity": float(pl.get("quantity", 1.0)),
                            "volume": float(pl.get("volume", 0.0)),
                            "weight": float(pl.get("weight", 0.0)),
                            "price": float(pl.get("price", 0.0)),
                        }
                        for pl in do_dict["product_lines"]
                        if isinstance(pl, dict)
                    ]

                return _success(
                    "PREFILL", "add_delivery_order", prefill_data,
                    "Data delivery order telah disiapkan. Silakan periksa dan simpan di form yang akan dibuka."
                )

            elif action_upper == "UPDATE":
                do_id = do_dict.get("id")
                do_num = do_dict.get("delivery_order_num")

                if not do_id and not do_num:
                    return _error("Untuk UPDATE, sertakan 'id' (integer) atau 'delivery_order_num' untuk mengidentifikasi order.")

                if not do_id and do_num:
                    sql_find = text("SELECT id FROM delivery_order WHERE delivery_order_num = :num AND is_deleted = false LIMIT 1")
                    with db._engine.connect() as conn:
                        row = conn.execute(sql_find, {"num": str(do_num)}).fetchone()
                    if not row:
                        return _error(f"Delivery order dengan nomor '{do_num}' tidak ditemukan.")
                    do_id = row[0]

                do_id = int(do_id)

                allowed_fields = {"status", "customer_id"}
                update_fields = {k: v for k, v in do_dict.items() if k in allowed_fields and v is not None}
                if not update_fields:
                    return _error("Tidak ada field yang dapat diubah. Field yang dapat diperbarui: status, customer_id.")

                if "status" in update_fields:
                    update_fields["status"] = str(update_fields["status"]).upper()

                prefill_data = {"id": do_id, **update_fields}

                return _success(
                    "PREFILL", "edit_delivery_order", prefill_data,
                    f"Data delivery order ID {do_id} siap diedit. Silakan periksa dan simpan perubahan di form."
                )

            return _error("Action tidak dikenal. Gunakan 'CREATE' atau 'UPDATE'.")
        except Exception as e:
            return _error(f"Terjadi kesalahan tak terduga: {str(e)}")

    return manage_delivery_order
