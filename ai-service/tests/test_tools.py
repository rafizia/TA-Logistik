import sys
import os
import pytest
from unittest.mock import MagicMock
from pydantic import ValidationError

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.system_control import system_control
from tools.manage_truck import get_manage_truck_tool
from tools.manage_location import get_manage_location_tool
from tools.manage_delivery_order import get_manage_delivery_order_tool


class TestSystemControl:
    def test_system_control(self):
        result = system_control.invoke({"target_page": "dashboard"})
        assert result["status"] == "success"
        assert result["ui_action"] == "NAVIGATE"
        assert result["target"] == "dashboard"
        assert result["entity_id"] is None

    def test_system_control_with_id(self):
        result = system_control.invoke({"target_page": "edit_truck", "entity_id": 456})
        assert result["status"] == "success"
        assert result["ui_action"] == "NAVIGATE"
        assert result["target"] == "edit_truck"
        assert result["entity_id"] == 456

    def test_system_control_missing_entity_id(self):
        with pytest.raises(ValidationError) as exc_info:
            system_control.invoke({"target_page": "edit_truck"})
        assert "Target page 'edit_truck' requires entity_id" in str(exc_info.value)

    def test_system_control_invalid_page_name(self):
        with pytest.raises(ValidationError):
            system_control.invoke({"target_page": "halaman_tidak_valid"})


class TestManageTruck:
    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        def mock_run(query: str):
            if "truck_type" in query:
                return "[(1, 'CDE'), (2, 'CDD'), (3, 'Blind Van')]"
            if "FROM dc" in query or "SELECT id, name FROM dc" in query:
                return "[(1, 'DC Jakarta'), (2, 'DC Surabaya')]"
            return "[]"
        db.run.side_effect = mock_run
        return db

    @pytest.fixture
    def manage_truck_tool(self, mock_db):
        return get_manage_truck_tool(mock_db)

    def test_create_truck(self, manage_truck_tool):
        data_input = {
            "action": "CREATE",
            "data": [{
                "plate_number": "B 1234 CD",
                "type_id": 1,
                "dc_id": 1,
                "max_individual_capacity_volume": 1200.0
            }]
        }
        result = manage_truck_tool.invoke(data_input)
        assert result["status"] == "success"
        assert result["ui_action"] == "PREFILL"
        assert result["target"] == "bulk_add_truck"
        assert result["data"][0]["plate_number"] == "B 1234 CD"

    def test_create_truck_with_name_resolution(self, manage_truck_tool):
        data_input = {
            "action": "CREATE",
            "data": [{
                "plate_number": "B 5678 EF",
                "type_name": "CDE",
                "dc_name": "DC Jakarta",
                "max_individual_capacity_volume": 1500.0
            }]
        }
        result = manage_truck_tool.invoke(data_input)
        assert result["status"] == "success"
        assert result["data"][0]["type_id"] == 1
        assert result["data"][0]["dc_id"] == 1

    def test_create_truck_missing_required_field(self, manage_truck_tool):
        # Missing max_individual_capacity_volume
        data_input = {
            "action": "CREATE",
            "data": [{
                "plate_number": "B 1234 CD",
                "type_id": 1,
                "dc_id": 1
            }]
        }
        result = manage_truck_tool.invoke(data_input)
        assert result["status"] == "error"
        assert "missing required field" in result["message"]

    def test_invalid_action(self, manage_truck_tool):
        with pytest.raises(ValidationError):
            manage_truck_tool.invoke({
                "action": "DELETE",
                "data": [{
                    "plate_number": "B 1234 CD",
                    "type_id": 1,
                    "dc_id": 1,
                    "max_individual_capacity_volume": 1000.0
                }]
            })

    def test_invalid_plate_number_format(self, manage_truck_tool):
        with pytest.raises(ValidationError) as exc_info:
            manage_truck_tool.invoke({
                "action": "CREATE",
                "data": [{
                    "plate_number": "INVALID_PLATE_FORMAT",
                    "type_id": 1,
                    "dc_id": 1,
                    "max_individual_capacity_volume": 1000.0
                }]
            })
        assert "Plate number format" in str(exc_info.value)

    def test_empty_data_list(self, manage_truck_tool):
        with pytest.raises(ValidationError) as exc_info:
            manage_truck_tool.invoke({
                "action": "CREATE",
                "data": []
            })
        assert "cannot be empty" in str(exc_info.value)

    def test_update_truck_allowed_fields(self, manage_truck_tool, mock_db):
        mock_db._engine.connect.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = (
            1, "B 1234 CD", 1, 1, 1000.0, "AVAILABLE", None
        )

        result = manage_truck_tool.invoke({
            "action": "UPDATE",
            "data": [{
                "plate_number": "B 1234 CD",
                "dc_name": "DC Jakarta",
                "first_status": "UNAVAILABLE"
            }]
        })

        assert result["status"] == "success"
        assert result["ui_action"] == "PREFILL"
        assert result["target"] == "bulk_edit_truck"
        assert result["data"][0]["first_status"] == "UNAVAILABLE"

    def test_update_truck_forbidden_field(self, manage_truck_tool):
        result = manage_truck_tool.invoke({
            "action": "UPDATE",
            "data": [{
                "plate_number": "B 1234 CD",
                "max_individual_capacity_volume": 9999.0  # not allowed
            }]
        })
        assert result["status"] == "error"
        assert "not allowed to be updated" in result["message"]


class TestManageLocation:
    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        def mock_run(query: str):
            if "customer" in query:
                return "[(1, 'PT ABC'), (2, 'PT XYZ')]"
            if "dc" in query:
                return "[(1, 'DC Jakarta'), (2, 'DC Surabaya')]"
            return "[]"
        db.run.side_effect = mock_run
        return db

    @pytest.fixture
    def manage_location_tool(self, mock_db):
        return get_manage_location_tool(mock_db)

    def test_create_location(self, manage_location_tool):
        data_input = {
            "action": "CREATE",
            "data": {
                "name": "Toko ABC",
                "address": "Jl. Merdeka 1",
                "provinsi": "DKI Jakarta",
                "kabupaten_kota": "Jakarta Pusat",
                "kecamatan": "Gambir",
                "desa_kelurahan": "Gambir",
                "kode_pos": "10110",
                "open_hour": "08:00",
                "close_hour": "17:00",
                "customer_id": 1,
                "dc_id": 1
            }
        }
        result = manage_location_tool.invoke(data_input)
        assert result["status"] == "success"
        assert result["ui_action"] == "PREFILL"
        assert result["target"] == "add_location"
        assert result["data"]["name"] == "Toko ABC"

    def test_create_location_with_name_resolution(self, manage_location_tool):
        data_input = {
            "action": "CREATE",
            "data": {
                "name": "Toko XYZ",
                "address": "Jl. Sudirman 2",
                "provinsi": "DKI Jakarta",
                "kabupaten_kota": "Jakarta Pusat",
                "kecamatan": "Gambir",
                "desa_kelurahan": "Gambir",
                "kode_pos": "10110",
                "open_hour": "08:00",
                "close_hour": "17:00",
                "customer_name": "PT ABC",
                "dc_name": "DC Jakarta"
            }
        }
        result = manage_location_tool.invoke(data_input)
        assert result["status"] == "success"
        assert result["data"]["customer_id"] == 1
        assert result["data"]["dc_id"] == 1

    def test_create_location_missing_required(self, manage_location_tool):
        data_input = {
            "action": "CREATE",
            "data": {
                "name": "Toko ABC",
                "address": "Jl. Merdeka 1"
            }
        }
        result = manage_location_tool.invoke(data_input)
        assert result["status"] == "error"
        assert "Missing required fields" in result["message"]

    def test_update_location(self, manage_location_tool):
        data_input = {
            "action": "UPDATE",
            "data": {
                "id": 10,
                "name": "Toko ABC Updated"
            }
        }
        result = manage_location_tool.invoke(data_input)
        assert result["status"] == "success"
        assert result["ui_action"] == "PREFILL"
        assert result["target"] == "edit_location"
        assert result["data"]["Id"] == 10


class TestManageDeliveryOrder:
    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        def mock_run(query: str):
            if "customer" in query:
                return "[(1, 'PT ABC'), (2, 'PT XYZ')]"
            if "FROM dc" in query or "SELECT id, name FROM dc" in query:
                return "[(1, 'DC Jakarta'), (2, 'DC Surabaya')]"
            if "product" in query:
                return "[(1, 'Produk A'), (2, 'Produk B')]"
            return "[]"
        db.run.side_effect = mock_run
        return db

    @pytest.fixture
    def manage_do_tool(self, mock_db):
        return get_manage_delivery_order_tool(mock_db)

    def test_create_delivery_order(self, manage_do_tool):
        data_input = {
            "action": "CREATE",
            "data": {
                "so_origin": "SO-001",
                "delivery_order_num": "DO-001",
                "eta_target": "2026-06-13T08:00:00",
                "status": "READY",
                "dc_id": 1,
                "customer_id": 2
            }
        }
        result = manage_do_tool.invoke(data_input)
        assert result["status"] == "success"
        assert result["ui_action"] == "PREFILL"
        assert result["target"] == "add_delivery_order"
        assert result["data"]["delivery_order_num"] == "DO-001"

    def test_create_delivery_order_with_name_resolution(self, manage_do_tool):
        data_input = {
            "action": "CREATE",
            "data": {
                "so_origin": "SO-002",
                "delivery_order_num": "DO-002",
                "eta_target": "2026-06-13T08:00:00",
                "status": "READY",
                "dc_name": "DC Jakarta",
                "customer_name": "PT ABC",
                "product_lines": [
                    {"product_name": "Produk A", "quantity": 5}
                ]
            }
        }
        result = manage_do_tool.invoke(data_input)
        assert result["status"] == "success"
        assert result["data"]["dc_id"] == 1
        assert result["data"]["customer_id"] == 1
        assert result["data"]["product_lines"][0]["product_id"] == 1

    def test_update_delivery_order(self, manage_do_tool):
        data_input = {
            "action": "UPDATE",
            "data": {
                "id": 5,
                "status": "DONE"
            }
        }
        result = manage_do_tool.invoke(data_input)
        assert result["status"] == "success"
        assert result["ui_action"] == "PREFILL"
        assert result["target"] == "edit_delivery_order"
        assert result["data"]["id"] == 5
        assert result["data"]["status"] == "DONE"


