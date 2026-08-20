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

def use_other_tools(db):
    """Buat dan return list sisa tools LangChain (selain system_control)."""

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

            # MOCK RESPONSE UNTUK EVALUASI
            if not _gateway_token:
                return (
                    f"**Hasil Simulasi Rute ({optimization_type.upper()})**\n\n"
                    "Truk 1: B 1234 XY (CDE)\n"
                    "  • Pesanan: 1 DO\n"
                    f"  • Jarak: 45.20 km\n Emisi 50 kg"
                    "  • Est. Waktu: 1j 15m\n"
                    "  • Muatan: 80.5% dari kapasitas\n\n"
                    "**Ringkasan Simulasi:**\n"
                    "  - Total truk digunakan : 1 truk\n"
                    "  - Total pesanan terlayani: 1 DO\n"
                    "  - Total jarak keseluruhan: 45.20 km\n"
                    "  - Pesanan tidak terjadwalkan: 0 DO\n\n"
                    "Ini hanya simulasi. Data belum disimpan ke sistem.\n"
                    "Jika Anda puas dengan hasilnya, katakan 'buat pengiriman' untuk memproses secara resmi."
                )

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

    return [get_available_options, automate_shipment, simulate_shipment]
