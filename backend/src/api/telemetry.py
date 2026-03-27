import os
import logging
from azure.monitor.opentelemetry import configure_azure_monitor

# Creates a logger for telemetry-related messages. This separates telemetry logs from our main application logs
logger = logging.getLogger("brand-guardian-telemetry")

def setup_telemetry():
    """
    Initializes Azure Monitor OpenTelemetry.
    """

    # RETRIEVE CONNECTION STRING 
    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not connection_string:
        logger.warning("No instrumentation key found. Telemetry is Disabled.")
        return
    
    # Configure the azure monitor
    try:
        configure_azure_monitor(
            connection_string=connection_string,
            logger_name = "brand-guardian-tracer"
        )
        logger.info(" Azure Monitor Tracking Enabled & Connected!")
    
    except Exception as e:
        # Function doesn't raise the error - telemetry failure shouldn't crash the app
        logger.error(f"Failed to initialize Azure Monitor: {e}")



