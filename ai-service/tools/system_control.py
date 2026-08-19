from typing import Optional, Literal
from pydantic import BaseModel, Field, model_validator
from langchain.tools import tool


TargetPage = Literal[
    "dashboard",
    "shipments_list", "add_shipment", "edit_shipment", "detail_shipment",
    "trucks_list", "add_truck", "bulk_add_truck", "edit_truck", "bulk_edit_truck",
    "delivery_orders_list", "add_delivery_order", "edit_delivery_order", "detail_delivery_order",
    "locations_list", "add_location", "edit_location", "detail_location", 
    "products_line_list",
    "products_list",
    "customers_list", "detail_customer",
    "users_list",
    "roles_list",
]

PAGES_REQUIRING_ID = {
    "edit_shipment", "detail_shipment",
    "edit_truck",
    "edit_delivery_order", "detail_delivery_order",
    "edit_location", "detail_location",
    "detail_customer",
}


class SystemControlInput(BaseModel):
    target_page: TargetPage = Field(description="Target page UI to navigate to.")
    entity_id: Optional[int] = Field(default=None, description="Optional entity ID for navigating to detail or edit pages (example: 123).")

    @model_validator(mode="after")
    def check_entity_id_required(self):
        if self.target_page in PAGES_REQUIRING_ID and self.entity_id is None:
            raise ValueError(f"Target page '{self.target_page}' requires entity_id")
        return self


@tool(args_schema=SystemControlInput)
def system_control(target_page: str, entity_id: Optional[int] = None) -> dict:
    """
    Use this tool for UI navigation.
    For pages following the 'edit_*' or 'detail_*' pattern, you MUST include the entity_id.
    If the entity_id is required but not available from the conversation context,
    DO NOT call this tool—ask the user for the entity ID or name first.
    """
    return {
        "status": "success",
        "ui_action": "NAVIGATE",
        "target": target_page,
        "entity_id": entity_id,
        "message": f"Mengarahkan Anda ke halaman {target_page.replace('_', ' ')}..."
    }
