"""
Hevo connector and domain knowledge.

Contains definitions of all supported sources, destinations, and validation logic
for pipeline configurations.
"""

from typing import Tuple, Optional, Dict, Set


# ============================================================================
# CONNECTOR DEFINITIONS
# ============================================================================

# All supported source connectors (150+)
SOURCES: Set[str] = {
    # Databases
    "MYSQL",
    "POSTGRES",
    "MONGODB",
    "SQL_SERVER",
    "ORACLE",
    "DYNAMODB",
    "DOCUMENTDB",
    "ELASTICSEARCH",
    "MARIADB",
    "COCKROACHDB",
    "COUCHDB",
    "CASSANDRA",
    "FIRESTORE",
    "FIREBASE_REALTIME",

    # Data Warehouses (as sources)
    "REDSHIFT",
    "BIGQUERY",

    # SaaS - Marketing
    "GOOGLE_ADS",
    "FACEBOOK_ADS",
    "HUBSPOT",
    "SALESFORCE_MARKETING_CLOUD",
    "MAILCHIMP",
    "LINKEDIN_ADS",
    "TIKTOK_ADS",
    "SNAPCHAT_ADS",
    "PINTEREST_ADS",
    "TWITTER_ADS",
    "MICROSOFT_ADS",
    "KLAVIYO",
    "ACTIVECAMPAIGN",
    "SENDGRID",
    "BRAZE",
    "ITERABLE",
    "MARKETO",
    "PARDOT",

    # SaaS - Sales & CRM
    "SALESFORCE",
    "ZENDESK",
    "FRESHDESK",
    "INTERCOM",
    "PIPEDRIVE",
    "HUBSPOT_CRM",
    "OUTREACH",
    "FRONT",
    "CLOSE",
    "COPPER",
    "ZOHO_CRM",

    # SaaS - Product & E-commerce
    "SHOPIFY",
    "WOOCOMMERCE",
    "STRIPE",
    "AMPLITUDE",
    "MIXPANEL",
    "SEGMENT",
    "PENDO",
    "BIGCOMMERCE",
    "MAGENTO",
    "RECHARGE",
    "GORGIAS",

    # SaaS - Engineering
    "GITHUB",
    "GITLAB",
    "JIRA",
    "ASANA",
    "TRELLO",
    "PAGERDUTY",
    "OPSGENIE",
    "DATADOG",
    "NEW_RELIC",
    "CLICKUP",
    "MONDAY",
    "NOTION",

    # SaaS - Finance
    "BRAINTREE",
    "CHARGEBEE",
    "RECURLY",
    "QUICKBOOKS",
    "XERO",
    "NETSUITE",
    "ZUORA",
    "SQUARE",
    "PAYPAL",

    # SaaS - Analytics & BI
    "GOOGLE_ANALYTICS",
    "GOOGLE_ANALYTICS_4",
    "FACEBOOK_INSIGHTS",
    "INSTAGRAM_INSIGHTS",
    "YOUTUBE_ANALYTICS",
    "LINKEDIN_PAGES",
    "TWITTER_ANALYTICS",
    "APPSFLYER",
    "ADJUST",
    "BRANCH",

    # File Storage & Cloud
    "S3",
    "GCS",
    "AZURE_BLOB",
    "SFTP",
    "FTP",
    "GOOGLE_SHEETS",
    "GOOGLE_DRIVE",
    "DROPBOX",
    "BOX",
    "ONEDRIVE",

    # Streaming & Events
    "KAFKA",
    "WEBHOOKS",
    "REST_API",
    "ANDROID_SDK",
    "IOS_SDK",
    "JAVASCRIPT_SDK",
    "KINESIS",
    "PUBSUB",

    # HR & Productivity
    "WORKDAY",
    "BAMBOOHR",
    "GREENHOUSE",
    "LEVER",
    "NAMELY",
    "GUSTO",
    "SLACK",
    "ZOOM",
    "MICROSOFT_TEAMS",
}

# All supported destination connectors
DESTINATIONS: Set[str] = {
    "SNOWFLAKE",
    "BIGQUERY",
    "REDSHIFT",
    "DATABRICKS",
    "POSTGRES",
    "MYSQL",
    "AURORA",
    "MS_SQL",
    "AZURE_SYNAPSE",
    "S3",
    "GCS",
    "FIREBOLT",
    "CLICKHOUSE",
}

# Connectors that can be BOTH source and destination
BIDIRECTIONAL: Set[str] = {
    "POSTGRES",
    "MYSQL",
    "REDSHIFT",
    "BIGQUERY",
    "S3",
    "GCS",
}

# Destination-only connectors (CANNOT be used as sources)
DESTINATION_ONLY: Set[str] = DESTINATIONS - BIDIRECTIONAL
# => {"SNOWFLAKE", "DATABRICKS", "AURORA", "MS_SQL", "AZURE_SYNAPSE", "FIREBOLT", "CLICKHOUSE"}


# ============================================================================
# CONNECTOR METADATA
# ============================================================================

CONNECTOR_INFO: Dict[str, Dict] = {
    # Databases
    "MYSQL": {
        "display_name": "MySQL",
        "category": "Database",
        "can_be_source": True,
        "can_be_destination": True,
    },
    "POSTGRES": {
        "display_name": "PostgreSQL",
        "category": "Database",
        "can_be_source": True,
        "can_be_destination": True,
    },
    "MONGODB": {
        "display_name": "MongoDB",
        "category": "Database",
        "can_be_source": True,
        "can_be_destination": False,
    },
    "SNOWFLAKE": {
        "display_name": "Snowflake",
        "category": "Data Warehouse",
        "can_be_source": False,
        "can_be_destination": True,
    },
    "BIGQUERY": {
        "display_name": "Google BigQuery",
        "category": "Data Warehouse",
        "can_be_source": True,
        "can_be_destination": True,
    },
    "REDSHIFT": {
        "display_name": "Amazon Redshift",
        "category": "Data Warehouse",
        "can_be_source": True,
        "can_be_destination": True,
    },
    "DATABRICKS": {
        "display_name": "Databricks",
        "category": "Data Warehouse",
        "can_be_source": False,
        "can_be_destination": True,
    },
    "SALESFORCE": {
        "display_name": "Salesforce",
        "category": "SaaS - CRM",
        "can_be_source": True,
        "can_be_destination": False,
    },
    "HUBSPOT": {
        "display_name": "HubSpot",
        "category": "SaaS - Marketing",
        "can_be_source": True,
        "can_be_destination": False,
    },
    "SHOPIFY": {
        "display_name": "Shopify",
        "category": "SaaS - E-commerce",
        "can_be_source": True,
        "can_be_destination": False,
    },
    "STRIPE": {
        "display_name": "Stripe",
        "category": "SaaS - Payments",
        "can_be_source": True,
        "can_be_destination": False,
    },
    "S3": {
        "display_name": "Amazon S3",
        "category": "Cloud Storage",
        "can_be_source": True,
        "can_be_destination": True,
    },
    "KAFKA": {
        "display_name": "Apache Kafka",
        "category": "Streaming",
        "can_be_source": True,
        "can_be_destination": False,
    },
}


# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

def normalize_connector_name(name: str) -> str:
    """
    Normalize connector name to standard format.

    Args:
        name: Connector name in any format

    Returns:
        Normalized uppercase name with underscores
    """
    return name.upper().strip().replace(" ", "_").replace("-", "_")


def is_valid_source(connector: str) -> bool:
    """
    Check if a connector can be used as a source.

    Args:
        connector: Connector name

    Returns:
        True if valid as source
    """
    normalized = normalize_connector_name(connector)
    return normalized in SOURCES


def is_valid_destination(connector: str) -> bool:
    """
    Check if a connector can be used as a destination.

    Args:
        connector: Connector name

    Returns:
        True if valid as destination
    """
    normalized = normalize_connector_name(connector)
    return normalized in DESTINATIONS


def validate_pipeline_direction(
    source_type: str,
    destination_type: str
) -> Tuple[bool, str]:
    """
    Validate that a source-to-destination pipeline configuration is valid.

    Args:
        source_type: Source connector type
        destination_type: Destination connector type

    Returns:
        Tuple of (is_valid, message)
    """
    if not source_type or not destination_type:
        return False, "Both source and destination types are required."

    source_normalized = normalize_connector_name(source_type)
    dest_normalized = normalize_connector_name(destination_type)

    # Check if source is a destination-only connector
    if source_normalized in DESTINATION_ONLY:
        return (
            False,
            f"{source_type} can only be used as a destination, not as a source. "
            f"Hevo does not support {source_type} as a data source."
        )

    # Check if source is valid
    if source_normalized not in SOURCES:
        return (
            False,
            f"{source_type} is not a supported source type. "
            "Please check the Hevo documentation for supported sources."
        )

    # Check if destination is valid
    if dest_normalized not in DESTINATIONS:
        return (
            False,
            f"{destination_type} is not a supported destination type. "
            f"Supported destinations: {', '.join(sorted(DESTINATIONS)[:5])}..."
        )

    return True, "Valid pipeline configuration."


def get_connector_info(connector: str) -> Optional[Dict]:
    """
    Get detailed information about a connector.

    Args:
        connector: Connector name

    Returns:
        Dict with connector info or None if not found
    """
    normalized = normalize_connector_name(connector)
    return CONNECTOR_INFO.get(normalized)


def get_source_categories() -> Dict[str, list]:
    """
    Get sources grouped by category.

    Returns:
        Dict mapping category names to lists of connectors
    """
    categories: Dict[str, list] = {}
    for connector, info in CONNECTOR_INFO.items():
        if info.get("can_be_source"):
            category = info.get("category", "Other")
            if category not in categories:
                categories[category] = []
            categories[category].append(info.get("display_name", connector))
    return categories


def get_destination_categories() -> Dict[str, list]:
    """
    Get destinations grouped by category.

    Returns:
        Dict mapping category names to lists of connectors
    """
    categories: Dict[str, list] = {}
    for connector, info in CONNECTOR_INFO.items():
        if info.get("can_be_destination"):
            category = info.get("category", "Other")
            if category not in categories:
                categories[category] = []
            categories[category].append(info.get("display_name", connector))
    return categories
