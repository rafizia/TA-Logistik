from typing import List, Literal
from pydantic import BaseModel, Field
from langchain.tools import tool


OptimizationType = Literal["distance", "emission", "load", "balance"]


class AutomateShipmentInput(BaseModel):
    optimization_type: OptimizationType = Field(
        description=(
            "Optimization strategy to use: "
            "'distance' (shortest route), 'emission' (lowest CO2 emissions), "
            "'load' (maximize truck load utilization), 'balance' (balance distance and load)."
        )
    )
    delivery_order_ids: List[int] = Field(
        description=(
            "List of delivery order integer IDs to include in the shipment (e.g. [3, 7, 15]). "
            "You MUST use sql_db_query first to find matching delivery order IDs with status = 'READY' "
            "and is_deleted = false before calling this tool."
        )
    )


def get_automate_shipment_tool(db):
    @tool(args_schema=AutomateShipmentInput)
    def automate_shipment(
        optimization_type: str,
        delivery_order_ids: list[int],
    ) -> dict:
        """
        Use this tool to automatically create an optimized shipment for a list of delivery order IDs.
        - optimization_type: 'distance', 'emission', 'load', or 'balance' (MANDATORY)
        - delivery_order_ids: list of integer IDs of delivery orders to include (MANDATORY).
          Always use sql_db_query first to retrieve valid order IDs (status = 'READY' AND is_deleted = false).
        """
        try:
            VALID_TYPES = {"distance", "emission", "load", "balance"}
            if not optimization_type or optimization_type not in VALID_TYPES:
                return {
                    "ui_action": "ERROR",
                    "message": (
                        "Missing or invalid 'optimization_type'. "
                        "Must be one of: 'distance', 'emission', 'load', or 'balance'. "
                        "Ask the user which optimization type they want."
                    )
                }

            if not delivery_order_ids or not isinstance(delivery_order_ids, list) or len(delivery_order_ids) == 0:
                return {
                    "ui_action": "ERROR",
                    "message": (
                        "Missing or empty 'delivery_order_ids'. "
                        "You MUST query the database first using sql_db_query to find matching delivery order IDs "
                        "with status = 'READY' and is_deleted = false, then pass those IDs to automate_shipment."
                    )
                }

            payload = {
                "optimization_type": optimization_type,
                "delivery_order_ids": [i for i in delivery_order_ids],
                "auto_submit": True,
            }

            return {
                "ui_action": "PREFILL",
                "target": "automate_shipment",
                "data": payload,
                "message": "Memulai proses pembuatan rute pengiriman otomatis berdasarkan kriteria Anda.",
            }
        except Exception as e:
            return {"ui_action": "ERROR", "message": f"ERROR: {str(e)}"}

    return automate_shipment
