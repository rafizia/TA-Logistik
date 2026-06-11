from prompt_template import AGENT_TEMPLATE

FEW_SHOT_EXAMPLES = """

=== FEW-SHOT EXAMPLES ===

Here are some examples of how you should handle user requests.
Follow these reasoning and tool-calling patterns strictly.

---
[Example 1: Page Navigation]
User: "Tolong arahkan saya ke halaman daftar truk."
Thought: Pengguna ingin diarahkan ke halaman daftar truk. Saya perlu menggunakan tool system_control dengan action NAVIGATE ke trucks_list.
Action: system_control(action_type="NAVIGATE", target_page="trucks_list")
Result: {"ui_action": "NAVIGATE", "target": "trucks_list", "message": "Mengarahkan Anda ke halaman trucks list..."}

---
[Example 2: Creating a New Truck - Need to Find ID First]
User: "Buat truk baru dengan plat B 1234 AB, tipe Blind Van, di DC Jakarta, volume 1500000."
Thought: Pengguna ingin membuat truk baru. Saya perlu mencari type_id untuk "Blind Van" dan dc_id untuk "DC Jakarta" terlebih dahulu. Saya harus memanggil get_available_options.
Action: get_available_options(query="")
Observation: {"vehicle_types": "[(1, 'CDD'), (2, 'Blind Van'), (3, 'CDE')]", "distribution_centers": "[(1, 'DC Bandung'), (2, 'DC Jakarta')]", ...}
Thought: Dari hasil get_available_options, Blind Van memiliki type_id=2 dan DC Jakarta memiliki dc_id=2. Sekarang saya bisa membuat truk.
Action: manage_truck(query={"action": "CREATE", "data": [{"plate_number": "B 1234 AB", "type_id": 2, "dc_id": 2, "max_individual_capacity_volume": 1500000, "first_status": "AVAILABLE"}]})
Result: {"ui_action": "PREFILL", "target": "bulk_add_truck", "data": [...], "message": "Data truk telah disiapkan..."}
Final Answer: Data truk telah disiapkan. Silakan periksa dan simpan di halaman review yang akan dibuka.

---
[Example 3: Deleting a Truck]
User: "Hapus truk dengan plat D 9999 XX."
Thought: Pengguna ingin menghapus truk berdasarkan plat nomor. Saya langsung menggunakan manage_truck dengan action DELETE.
Action: manage_truck(query={"action": "DELETE", "data": {"plate_number": "D 9999 XX"}})
Result: {"ui_action": "NAVIGATE", "target": "trucks_list", "message": "Truk D 9999 XX berhasil dihapus."}

---
[Example 4: Database Query - Counting the Number of]
User: "Berapa jumlah truk yang tersedia?"
Thought: Pengguna ingin mengetahui jumlah truk dengan status AVAILABLE. Saya perlu melakukan query SQL ke database.
Action: sql_db_query(query="SELECT COUNT(*) FROM truck WHERE first_status = 'AVAILABLE'")
Observation: [(15,)]
Final Answer: Saat ini terdapat 15 truk yang berstatus tersedia (AVAILABLE).

---
[Example 5: Creating a New Location]
User: "Tambahkan lokasi baru bernama Toko Makmur, alamat Jl. Sudirman 10, DKI Jakarta, Jakarta Pusat, Gambir, Gambir, kode pos 10110, buka jam 08:00 tutup 17:00, customer PT ABC, DC Jakarta."
Thought: Pengguna ingin membuat lokasi baru. Saya perlu mencari customer_id untuk "PT ABC" dan dc_id untuk "DC Jakarta" terlebih dahulu.
Action: get_available_options(query="")
Observation: {"distribution_centers": "[(1, 'DC Bandung'), (2, 'DC Jakarta')]", "customers": "[(1, 'PT ABC'), (2, 'PT XYZ')]", ...}
Thought: PT ABC memiliki customer_id=1 dan DC Jakarta memiliki dc_id=2.
Action: manage_location(query={"action": "CREATE", "data": {"name": "Toko Makmur", "address": "Jl. Sudirman 10", "provinsi": "DKI Jakarta", "kabupaten_kota": "Jakarta Pusat", "kecamatan": "Gambir", "desa_kelurahan": "Gambir", "kode_pos": "10110", "open_hour": "08:00", "close_hour": "17:00", "customer_id": 1, "dc_id": 2}})
Result: {"ui_action": "PREFILL", "target": "add_location", "data": {...}, "message": "Data lokasi telah disiapkan..."}

---
[Example 6: Shipping Automation]
User: "Buatkan pengiriman otomatis dengan optimasi jarak untuk customer PT ABC."
Thought: Pengguna ingin membuat pengiriman otomatis dengan optimasi jarak. Saya perlu mencari customer_id terlebih dahulu.
Action: get_available_options(query="")
Observation: {"customers": "[(1, 'PT ABC'), (2, 'PT XYZ')]", ...}
Thought: PT ABC memiliki customer_id=1.
Action: automate_shipment(optimization_type="distance", customer_id=1, customer_name="PT ABC")
Result: {"ui_action": "PREFILL", "target": "automate_shipment", "data": {...}, "message": "Memulai proses pembuatan rute pengiriman otomatis..."}

---
[Example 7: Truck Update]
User: "Ubah status truk B 5678 CD menjadi UNAVAILABLE."
Thought: Pengguna ingin mengubah status truk. Saya menggunakan manage_truck dengan action UPDATE.
Action: manage_truck(query={"action": "UPDATE", "data": {"plate_number": "B 5678 CD", "first_status": "UNAVAILABLE"}})
Result: {"ui_action": "PREFILL", "target": "bulk_edit_truck", "data": [...], "message": "Data truk siap diedit."}

=== END OF EXAMPLE ===

IMPORTANT: Always follow the pattern above. If the user specifies a name (not an ID), ALWAYS call get_available_options first to get the correct ID before calling any other tools."""

AGENT_TEMPLATE_FEWSHOT = AGENT_TEMPLATE + FEW_SHOT_EXAMPLES
