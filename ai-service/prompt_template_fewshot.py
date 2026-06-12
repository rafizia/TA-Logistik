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

---
[Example 11: Create Delivery Order - Basic]
User: "Buat order baru dengan SO SO-TEST, nomor DO DO-TEST, customer PT ABC, DC Jakarta, status READY, ETA 2026-06-15."
Thought: Pengguna ingin membuat delivery order baru. Saya perlu mencari dc_id untuk "DC Jakarta" dan customer_id untuk "PT ABC" terlebih dahulu dengan get_available_options.
Action: get_available_options(query="")
Observation: {"distribution_centers": "[(1, 'DC Bandung'), (2, 'DC Jakarta')]", "customers": "[(1, 'PT ABC'), (2, 'PT XYZ')]", ...}
Thought: DC Jakarta memiliki dc_id=2 dan PT ABC memiliki customer_id=1. ETA adalah 2026-06-15. Sekarang saya panggil manage_delivery_order.
Action: manage_delivery_order(query={"action": "CREATE", "data": {"so_origin": "SO-TEST", "delivery_order_num": "DO-TEST", "eta_target": "2026-06-15T08:00:00", "status": "READY", "dc_id": 2, "customer_id": 1}})
Result: {"ui_action": "PREFILL", "target": "create_delivery_order", "data": {...}, "message": "Data delivery order telah disiapkan..."}
Final Answer: Data delivery order telah disiapkan. Silakan periksa dan simpan di form yang akan dibuka.

---
[Example 12: Create Delivery Order - With Products]
User: "Buat order DO-456 dari DC Bandung untuk PT XYZ, SO SO-456, status PENDING, ETA besok, muatannya produk Air Mineral 500ml sebanyak 100 unit, volume 2 m3, berat 50 kg, harga 500000."
Thought: Pengguna ingin membuat delivery order dengan produk. Saya perlu mencari dc_id, customer_id, dan product_id terlebih dahulu.
Action: get_available_options(query="")
Observation: {"distribution_centers": "[(1, 'DC Bandung'), (2, 'DC Jakarta')]", "customers": "[(1, 'PT ABC'), (2, 'PT XYZ')]", ...}
Thought: DC Bandung=1, PT XYZ=2. Sekarang saya cari product_id untuk "Air Mineral 500ml".
Action: sql_db_query(query="SELECT id, name FROM product WHERE name ILIKE '%Air Mineral 500ml%' LIMIT 5")
Observation: [(5, 'Air Mineral 500ml')]
Thought: product_id=5. Tanggal besok adalah 2026-06-13. Sekarang saya panggil manage_delivery_order dengan product_lines.
Action: manage_delivery_order(query={"action": "CREATE", "data": {"so_origin": "SO-456", "delivery_order_num": "DO-456", "eta_target": "2026-06-13T08:00:00", "status": "PENDING", "dc_id": 1, "customer_id": 2, "product_lines": [{"product_id": 5, "quantity": 100, "volume": 2.0, "weight": 50.0, "price": 500000.0}]}})
Result: {"ui_action": "PREFILL", "target": "create_delivery_order", "data": {...}, "message": "Data delivery order telah disiapkan..."}
Final Answer: Data delivery order telah disiapkan. Silakan periksa dan simpan di form yang akan dibuka.

---
[Example 13: Create Delivery Order - Missing Fields, MUST ASK FIRST (DC known from context)]
System Context: [SYSTEM CONTEXT] The current user is logged in as role 'Admin DC'. Their Distribution Center (DC) is fixed: dc_id=2, dc_name='DC Banten'.
User: "Buat order DO-COBA, SO SO-COBA."
Thought: Pengguna ingin membuat delivery order. Saya harus memeriksa apakah semua field wajib sudah ada.
Checklist field wajib:
  1. so_origin -> SO-COBA ✓
  2. delivery_order_num -> DO-COBA ✓
  3. eta_target -> TIDAK ADA ✗
  4. status -> TIDAK ADA ✗
  5. dc_id -> SUDAH DIKETAHUI dari SYSTEM CONTEXT: dc_id=2 (DC Banten) ✓ — jangan tanya ini ke user
  6. customer_id (customer/tujuan) -> TIDAK ADA ✗
Kesimpulan: Ada 3 field yang belum disebutkan (eta_target, status, customer). DC sudah diketahui dari konteks. Saya HARUS berhenti dan bertanya dulu. JANGAN panggil tool apapun.
Final Answer: Untuk membuat delivery order DO-COBA, saya masih membutuhkan informasi berikut:
- **Customer/tujuan pengiriman** (nama customer)
- **Target ETA** (tanggal dan waktu pengiriman)
- **Status awal order** (READY, PENDING, RUNNING, DONE, atau IN_CALCULATION)
Mohon lengkapi informasi tersebut.

---
[Example 14: Create Delivery Order - Partial Info, Continue Asking (DC auto-filled)]
System Context: [SYSTEM CONTEXT] The current user's DC is fixed: dc_id=2, dc_name='DC Banten'.
User: "DO-COBA, SO SO-COBA, customer PT ABC."
Thought: Saya memeriksa field wajib:
  1. so_origin -> SO-COBA ✓
  2. delivery_order_num -> DO-COBA ✓
  3. eta_target -> TIDAK ADA ✗
  4. status -> TIDAK ADA ✗
  5. dc_id -> dari SYSTEM CONTEXT: dc_id=2 ✓ — tidak perlu tanya
  6. customer_id (PT ABC) -> ada nama, perlu resolve ✓
Masih ada 2 field yang belum disebutkan (eta_target dan status). Saya HARUS bertanya dulu.
Final Answer: Terima kasih! Saya masih membutuhkan 2 informasi lagi:
- **Target ETA** (tanggal dan waktu pengiriman, contoh: 2026-06-15 atau besok)
- **Status awal order** (READY, PENDING, RUNNING, DONE, atau IN_CALCULATION)

=== END OF EXAMPLE ===

IMPORTANT: Always follow the pattern above. If the user specifies a name (not an ID), ALWAYS call get_available_options first to get the correct ID before calling any other tools.
IMPORTANT: When the user provides specific delivery order IDs (e.g., "order ID 5", "DO ID 5 dan 12"), use the delivery_order_ids parameter directly. Do NOT use other filters when specific IDs are given.
IMPORTANT: When the user describes delivery orders by attributes (e.g., eta_target, volume, destination city), use the QUERY-FIRST pattern: first query the database with sql_db_query to find matching IDs, then pass them to automate_shipment via delivery_order_ids. Always include status = 'READY' AND is_deleted = false in your WHERE clause.
IMPORTANT: For manage_delivery_order CREATE, if ANY of the 6 mandatory fields (so_origin, delivery_order_num, eta_target, status, dc_id, customer_id) are missing, you MUST ask the user for them BEFORE calling any tool. Never guess or assume missing values."""

AGENT_TEMPLATE_FEWSHOT = AGENT_TEMPLATE + FEW_SHOT_EXAMPLES
