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

---
[Example 8: Shipping Automation with Specific Delivery Order IDs]
User: "Buatkan shipment untuk order ID 5 dan 12 dengan optimasi jarak."
Thought: Pengguna ingin membuat pengiriman otomatis untuk delivery order ID spesifik (5 dan 12) dengan optimasi jarak. Saya bisa langsung menggunakan parameter delivery_order_ids tanpa perlu mencari filter lain.
Action: automate_shipment(optimization_type="distance", delivery_order_ids=[5, 12])
Result: {"ui_action": "PREFILL", "target": "automate_shipment", "data": {...}, "message": "Memulai proses pembuatan rute pengiriman otomatis..."}

---
[Example 9: Query-First Pattern - Shipment by ETA Target]
User: "Buat shipment untuk order yang eta targetnya besok dengan optimasi emisi."
Thought: Pengguna ingin membuat pengiriman untuk delivery order berdasarkan eta_target. Parameter ini tidak tersedia langsung di automate_shipment, jadi saya perlu query database dulu untuk mencari ID order yang sesuai. Tanggal besok adalah 2026-06-12.
Action: sql_db_query(query="SELECT id FROM delivery_order WHERE eta_target::date = '2026-06-12' AND status = 'READY' AND is_deleted = false")
Observation: [(3,), (7,), (15,)]
Thought: Ditemukan 3 delivery order dengan eta_target besok: ID 3, 7, dan 15. Sekarang saya gunakan delivery_order_ids untuk membuat shipment.
Action: automate_shipment(optimization_type="emission", delivery_order_ids=[3, 7, 15])
Result: {"ui_action": "PREFILL", "target": "automate_shipment", "data": {...}, "message": "Memulai proses pembuatan rute pengiriman otomatis..."}
Final Answer: Pratinjau pengiriman berhasil dibuat! Mengalihkan ke halaman tinjauan pengiriman...

---
[Example 10: Query-First Pattern - Shipment by Destination Attribute]
User: "Buatkan pengiriman untuk semua order yang tujuannya di Bandung, pakai optimasi jarak."
Thought: Pengguna ingin membuat pengiriman berdasarkan lokasi tujuan. Saya perlu query database dengan JOIN ke tabel location untuk mencari delivery order yang tujuannya di Bandung.
Action: sql_db_query(query="SELECT del_ord.id FROM delivery_order del_ord JOIN location loc ON del_ord.loc_dest_id = CAST(loc.id AS TEXT) WHERE loc.kabupaten_kota ILIKE '%Bandung%' AND del_ord.status = 'READY' AND del_ord.is_deleted = false")
Observation: [(8,), (22,)]
Thought: Ditemukan 2 delivery order dengan tujuan Bandung: ID 8 dan 22. Sekarang saya gunakan delivery_order_ids.
Action: automate_shipment(optimization_type="distance", delivery_order_ids=[8, 22])
Result: {"ui_action": "PREFILL", "target": "automate_shipment", "data": {...}, "message": "Memulai proses pembuatan rute pengiriman otomatis..."}
Final Answer: Pratinjau pengiriman berhasil dibuat! Mengalihkan ke halaman tinjauan pengiriman...

=== END OF EXAMPLE ===

IMPORTANT: Always follow the pattern above. If the user specifies a name (not an ID), ALWAYS call get_available_options first to get the correct ID before calling any other tools.
IMPORTANT: When the user provides specific delivery order IDs (e.g., "order ID 5", "DO ID 5 dan 12"), use the delivery_order_ids parameter directly. Do NOT use other filters when specific IDs are given.
IMPORTANT: When the user describes delivery orders by attributes (e.g., eta_target, volume, destination city), use the QUERY-FIRST pattern: first query the database with sql_db_query to find matching IDs, then pass them to automate_shipment via delivery_order_ids. Always include status = 'READY' AND is_deleted = false in your WHERE clause."""

AGENT_TEMPLATE_FEWSHOT = AGENT_TEMPLATE + FEW_SHOT_EXAMPLES

