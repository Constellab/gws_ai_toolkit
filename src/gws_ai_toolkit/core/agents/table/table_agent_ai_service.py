"""
Service for managing TableAgentAI instances and creating scenarios to replay agent interactions.

This service provides functionality to save a TableAgentAI's state (including all tables and
conversation history) and automatically create and execute a scenario that can replay the
agent's transformations on new data.
"""

from gws_core import (
    ConfigParamsDict,
    OutputTask,
    ProtocolProxy,
    ResourceModel,
    ResourceOrigin,
    ScenarioProxy,
    Table,
)

from gws_ai_toolkit.core.agents.base_function_agent_events import (
    CreateSubAgent,
    FunctionCallEvent,
    ResponseFullTextEvent,
    SubAgentSuccess,
)
from gws_ai_toolkit.core.agents.table.table_agent_ai import TableAgentAi
from gws_ai_toolkit.core.agents.table.table_agent_ai_events import SerializableTableAgentEvent
from gws_ai_toolkit.core.agents.table.table_agent_event_base import (
    UserQueryMultiTablesEvent,
)
from gws_ai_toolkit.core.agents.table.table_agent_replay_task import TableAgentReplayTask


class TableAgentAiService:
    """Service for managing TableAgentAI instances and scenarios."""

    @classmethod
    def serialize_events(cls, table_agent_ai: TableAgentAi) -> list[SerializableTableAgentEvent]:
        """Serialize agent events and extract input tables.

        This method converts the agent's event list to a serializable format by:
        1. Filtering events to get only the main agent's events (not sub-agent events)
        2. Converting UserQueryTable events to their serializable counterparts (using table keys)
        3. Keeping only the serializable event types (FunctionCallEvent, ResponseFullTextEvent, etc.)
        4. Extracting all input tables that need to be saved

        Args:
            table_agent_ai: The TableAgentAI instance to serialize

        Returns:
            Tuple of (serializable_events, input_tables_dict)
        """
        # Get all events from the agent
        all_events = table_agent_ai.get_events().get_all()

        serializable_events: list[SerializableTableAgentEvent] = []

        # Filter and convert events
        for event in all_events:
            # Only serialize the user query from the main agent (the sub user query are generated)
            if isinstance(event, UserQueryMultiTablesEvent) and event.agent_id == table_agent_ai.id:
                serializable_event = event.to_serializable()
                serializable_events.append(serializable_event)

            # For BaseFunctionWithSubAgentSerializableEvent types
            # These are already serializable, just add them
            elif isinstance(event, (FunctionCallEvent, ResponseFullTextEvent, CreateSubAgent, SubAgentSuccess)):
                serializable_events.append(event)

        return serializable_events

    @classmethod
    def save_table_agent_ai(
        cls,
        table_agent_ai: TableAgentAi,
        scenario_title: str = "Table Agent Replay",
    ) -> ResourceModel:
        """
        Save a TableAgentAI's state by creating and running a scenario with the TableAgentReplayTask.

        This method takes a TableAgentAI instance with its conversation history (events) and creates
        a scenario that can replay these transformations. The scenario uses the TableAgentReplayTask
        to process an input ResourceSet through the saved event sequence.

        The method handles:
        1. Serializing agent events (converting Table objects to table keys)
        2. Extracting input tables that need to be saved
        3. Creating a ResourceSet from input tables
        4. Creating and running a scenario with the replay task

        Args:
            table_agent_ai: The TableAgentAI instance containing tables and agent state
            scenario_title: Title for the created scenario (default: "Table Agent Replay")

        Returns:
            ResourceModel: The output ResourceSet resource model containing all transformed tables

        Raises:
            Exception: If the scenario fails to run or if resources are invalid

        Example:
            >>> agent = TableAgentAi(openai_api_key="key", model="gpt-4o", temperature=0.1)
            >>> # Add tables and interact with agent
            >>> for event in agent.call_agent(user_query):
            ...     pass
            >>> # Save the agent state and run replay
            >>> output_model = TableAgentAiService.save_table_agent_ai(agent, "My Transformation")
        """

        # Step 1: Serialize events and extract input tables
        serializable_events = cls.serialize_events(table_agent_ai)

        # Step 2: Create ResourceSet from input tables
        # For now, we'll create it in memory - you need to implement the save logic
        table_models = cls.create_table_resources(table_agent_ai.get_input_tables(), "Agent Input Tables")

        # Step 3: Create a scenario to run the TableAgentReplayTask
        scenario: ScenarioProxy = ScenarioProxy(title=scenario_title)
        protocol: ProtocolProxy = scenario.get_protocol()

        # Prepare config for the replay task with serialized events
        config: ConfigParamsDict = {
            "serialized_events": [event.to_json_dict() for event in serializable_events],
            "model": table_agent_ai._model,
            "temperature": table_agent_ai._temperature,
        }

        # Add the TableAgentReplayTask
        replay_task = protocol.add_process(TableAgentReplayTask, "replay_task", config)

        # Add the input resource (ResourceSet with tables) and connect it
        resource_ids = [model.id for model in table_models.values()]
        protocol.add_resources_to_process_dynamic_input(
            resource_model_ids=resource_ids, process_instance_name="replay_task"
        )

        # Add output task to capture the results and connect it
        output_task = protocol.add_output("output", replay_task >> "output_resource_set")

        # Run the scenario
        scenario.run(auto_delete_if_error=True)

        # Return the resource model of the output ResourceSet
        output_task.refresh()
        return output_task.get_input_resource_model(OutputTask.input_name)

    @classmethod
    def create_table_resources(
        cls, tables: dict[str, Table], resource_set_name: str = "Agent Tables"
    ) -> dict[str, ResourceModel]:
        resource_models = {}

        for table_name, table in tables.items():
            model_id = table.get_model_id()
            table.name = table_name

            if model_id is None:
                # Save the table if not already saved
                model = ResourceModel.save_from_resource(table, origin=ResourceOrigin.UPLOADED)
                resource_models[table_name] = model
            else:
                # Table already saved, just get the model
                resource_models[table_name] = ResourceModel.get_by_id_and_check(model_id)

        return resource_models
