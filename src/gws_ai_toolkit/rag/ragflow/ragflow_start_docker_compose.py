import os

from gws_core import (ConfigParams, ConfigSpecs, InputSpecs, OutputSpecs, Task,
                      TaskInputs, TaskOutputs, TypingStyle, task_decorator)
from gws_core.docker.docker_service import DockerService


@task_decorator(
    "RagflowStartDockerCompose",
    human_name="Start RagFlow Docker Compose",
    short_description="Start the RagFlow docker compose services",
    style=TypingStyle.community_image("ragflow", "#4A90E2")
)
class RagflowStartDockerCompose(Task):
    """
    Start the RagFlow docker compose services.

    This task starts the complete RagFlow infrastructure using docker compose,
    including all required services:
    - **MySQL**: Database for storing RagFlow data
    - **Redis**: In-memory cache for session and task management
    - **MinIO**: Object storage for documents and embeddings
    - **Elasticsearch**: Search engine for vector similarity and full-text search
    - **RagFlow Server**: Main RagFlow application server

    The docker compose configuration is registered with the Constellab docker service,
    allowing centralized management and monitoring of the RagFlow infrastructure.

    ## Usage

    This task requires no inputs or configuration. Simply run it to start the
    RagFlow services. The task will wait for all services to be ready before completing.

    ## Notes

    - The docker compose files are located in the `docker` subfolder relative to this task
    - Services are registered with unique name "ragflow" under brick "gws_ai_toolkit"
    - The task waits for all services to reach "running" status before completing
    - If services are already running, the task will complete immediately
    """

    input_specs = InputSpecs()
    output_specs = OutputSpecs()
    config_specs = ConfigSpecs()

    def run(self, params: ConfigParams, inputs: TaskInputs) -> TaskOutputs:
        """Start the RagFlow docker compose services.

        Parameters
        ----------
        params : ConfigParams
            Configuration parameters (none required)
        inputs : TaskInputs
            Task inputs (none required)

        Returns
        -------
        TaskOutputs
            Empty outputs dictionary
        """
        # Get the path to the docker folder
        docker_folder_path = os.path.join(os.path.dirname(__file__), "docker")

        self.log_info_message("Registering RagFlow docker compose services...")

        # Register the docker compose with the Docker service
        docker_service = DockerService()
        docker_service.register_sub_compose_from_folder(
            brick_name="gws_ai_toolkit",
            unique_name="ragflow",
            folder_path=docker_folder_path,
            description="RagFlow docker compose services"
        )

        self.log_info_message("Waiting for RagFlow services to be ready...")

        # Wait for the compose to be ready
        docker_service.wait_for_compose_status(
            brick_name="gws_ai_toolkit",
            unique_name="ragflow"
        )

        self.log_success_message("RagFlow docker compose services started successfully!")

        return {}
