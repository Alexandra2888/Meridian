from app.clients.crm.base import CRMClient, get_crm_client
from app.clients.crm.hubspot import HubSpotCRMClient
from app.clients.crm.stub import StubCRMClient

__all__ = ["CRMClient", "HubSpotCRMClient", "StubCRMClient", "get_crm_client"]
