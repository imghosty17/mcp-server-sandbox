from mcp.server.fastmcp import FastMCP
import os
from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication
from dotenv import load_dotenv
from azure.devops.v7_1.core import CoreClient
from azure.devops.v7_1.operations import OperationsClient
from azure.devops.v7_1.core.models import TeamProject
import time

# Load environment variables from a .env file
load_dotenv()

mcp = FastMCP("ado")


# Function to fetch Azure DevOps clients
async def get_azure_clients():
    personal_access_token = os.getenv("AZURE_DEVOPS_DESTINATION_PAT_TOKEN")
    organization_name = os.getenv("AZURE_DEVOPS_DESTINATION_ORGANIZATION")

    if not personal_access_token or not organization_name:
        raise ValueError("Missing Azure DevOps credentials in environment variables.")

    organization_url = f"https://dev.azure.com/{organization_name}"
    credentials = BasicAuthentication("", personal_access_token)
    connection = Connection(base_url=organization_url, creds=credentials)

    try:
        # Return a dictionary of various Azure DevOps client objects
        return {
            "core_client": connection.clients.get_core_client(),
            "operations_client": connection.clients.get_operations_client(),
        }
    except Exception as e:
        raise Exception(f"Failed to create Azure DevOps clients: {e}")


async def check_project_exist(project_name: str, core_client: CoreClient) -> bool:
    projects  = core_client.get_projects()
    return any(project.name.lower() == project_name.lower() for project in projects)


@mcp.tool()
async def create_project(project_name: str):
    """
    Create a new Azure DevOps project with the specified name.

    This function checks if a project with the given name already exists. If it does not exist,
    it creates a new project with default settings.

    Args:
        project_name (str): The name of the project to create.

    Returns:
        str: A message indicating the result of the project creation attempt.
            - If the project already exists: "{project_name} Already Exist Project"
            - If creation is successful: "{project_name} Created Successfully"
            - If creation fails: "{project_name} Failed to create."
    """
    clients = await get_azure_clients()
    core_client: CoreClient = clients["core_client"]
    operations_client: OperationsClient = clients["operations_client"]

    # Check if the project already exists
    if await check_project_exist(project_name, core_client):
        return f"{project_name} Already Exist Project"

    # Define the new project
    new_project = TeamProject(
        name=project_name,
        description="Project created using MCP",
        visibility="private",
        capabilities={
            "versioncontrol": {"sourceControlType": "Git"},
            "processTemplate": {
                "templateTypeId": "b8a3a935-7e91-48b8-a94c-606d37c3e9f2"
            },
        },
    )

    # Queue the project creation operation
    operation = core_client.queue_create_project(new_project)

    # Wait for the operation to complete
    while operation.status not in ["succeeded", "failed", "cancelled"]:
        operation = operations_client.get_operation(operation.id)
        time.sleep(5)

    # Return the result based on the operation status
    if operation.status == "succeeded":
        return f"{project_name} Created Successfully"
    else:
        return f"{project_name} Failed to create."


if __name__ == "__main__":
    mcp.run(transport="stdio")
