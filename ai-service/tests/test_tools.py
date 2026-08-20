import sys
import os
import pytest
from unittest.mock import MagicMock
from pydantic import ValidationError

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.system_control import system_control
from tools.manage_truck import get_manage_truck_tool


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
