import sys
import os
import pytest
from pydantic import ValidationError

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.system_control import system_control


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
