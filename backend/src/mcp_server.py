"""
KnowMat MCP Server - Material Design Tools

Exposes tools for alloy property prediction and database queries.
Used by the dependency-aware planning engine for multi-step workflows.
"""
import mcp
import os
import logging
from dotenv import load_dotenv
from local_models import local_model_inference
from dbmanager import DBManager

logging.basicConfig(
    filename="log_mcp_server.log",
    encoding="utf-8",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()

mcp_server = mcp.server.fastmcp.FastMCP("mcp_server")
db_manager = DBManager(
    host=os.environ.get("DB_HOST", "localhost"),
    port=int(os.environ.get("DB_PORT", "5432")),
    user=os.environ.get("DB_USER", ""),
    password=os.environ.get("DB_PWD", ""),
    database=os.environ.get("DB_NAME", "postgres")
)


@mcp_server.tool()
def predict_alloy_harmful_phases(alloy_compositions: str) -> bool:
    """Predict whether harmful phases precipitate during aging heat treatment."""
    result = False
    result = local_model_inference(model_id="gbc-class", tab=alloy_compositions)
    return result


@mcp_server.tool()
def predict_alloy_gamma_prime_solvus_temperature(alloy_compositions: str) -> dict:
    """Predict γ' phase solvus temperature from alloy composition."""
    result = local_model_inference(model_id="svr-regressor", tab=alloy_compositions)
    return result if isinstance(result, dict) else {"value": result, "unit": "℃"}


@mcp_server.tool()
def predict_alloy_density(alloy_compositions: str) -> dict:
    """Predict alloy density from composition."""
    result = local_model_inference(model_id="gbr-density", tab=alloy_compositions)
    return result if isinstance(result, dict) else {"value": result, "unit": "g/cm3"}


@mcp_server.tool()
def predict_alloy_liquidus_temperature(alloy_compositions: str) -> dict:
    """Predict liquidus temperature from composition."""
    result = local_model_inference(model_id="gbr-liquidus", tab=alloy_compositions)
    return result if isinstance(result, dict) else {"value": result, "unit": "℃"}


@mcp_server.tool()
def predict_alloy_solidus_temperature(alloy_compositions: str) -> dict:
    """Predict solidus temperature from composition."""
    result = local_model_inference(model_id="svr-solidus", tab=alloy_compositions)
    return result if isinstance(result, dict) else {"value": result, "unit": "℃"}


@mcp_server.tool()
def predict_alloy_gamma_prime_size(alloy_compositions: str, heat_treatment_information: str) -> dict:
    """Predict γ' phase size from composition and heat treatment."""
    result = local_model_inference(
        model_id="gbr-size",
        tab=alloy_compositions + ',' + heat_treatment_information
    )
    return result if isinstance(result, dict) else {"value": result, "unit": "mm"}


@mcp_server.tool()
def predict_alloy_misfit(alloy_compositions: str, testing_temperature: str) -> dict:
    """Predict γ/γ' misfit from composition and testing temperature."""
    result = local_model_inference(
        model_id="gbr-misfit",
        tab=alloy_compositions + ',' + f'testing_temperature:{testing_temperature}'
    )
    return {"value": result, "unit": ""} if not isinstance(result, dict) else result


@mcp_server.tool()
def query_database(sql: str) -> str:
    """
    Execute SQL query on the alloy database.
    Schema: alloys(alloy_id, data_id, name, ...), compositions(composition_id, alloy_id, element, unit, value).
    """
    db_manager.connect()
    records = db_manager.execute_sql(sql=sql)
    db_manager.close()
    logger.info(f"SQL Query: {sql}")
    logger.info(f"Query Result: {str(records)}")
    return str(records)


if __name__ == "__main__":
    mcp_server.run(transport='stdio')
