from typing import List

from gws_ai_toolkit.rag.ragflow.ragflow_service import RagFlowService
from gws_core import (ConfigParams, ConfigSpecs, CredentialsDataOther,
                      CredentialsParam, CredentialsType, DynamicInputs, File,
                      Folder, FSNode, InputSpec, OutputSpecs, ResourceList,
                      StrParam, Task, TaskInputs, TaskOutputs, TypingStyle,
                      task_decorator)


@task_decorator("RagFlowSendFileToDataset", human_name="Send files to RagFlow Dataset",
                short_description="Send as many files or folders as you want to RagFlow Dataset",
                style=TypingStyle.community_image("ragflow", "#4A90E2"))
class RagFlowSendFileToDataset(Task):
    """
    Send as many files or folders as you want to RagFlow Dataset.

    A RagFlow API key and a RagFlow dataset id are required to send files to the RagFlow Dataset.
    """

    input_specs = DynamicInputs(
        additionnal_port_spec=InputSpec(FSNode, human_name="Files or folders",
                                        short_description="Files or folders to send to RagFlow Dataset"),
    )
    output_specs = OutputSpecs()

    config_specs = ConfigSpecs({
        'api_key': CredentialsParam(credentials_type=CredentialsType.OTHER,
                                    human_name="RagFlow API Key",
                                    short_description="A credentials that contains 'route' and 'api_key'",
                                    ),
        'dataset_id': StrParam(human_name="RagFlow dataset id",
                               short_description="Id of the RagFlow dataset where to send the files",
                               )
    })

    def run(self, params: ConfigParams, inputs: TaskInputs) -> TaskOutputs:
        """ Run the task """

        fs_nodes: ResourceList = inputs[DynamicInputs.SPEC_NAME]

        credentials: CredentialsDataOther = params.get_value('api_key')
        ragflow_service = RagFlowService.from_credentials(credentials)

        file_paths: List[str] = []

        for fs_node in fs_nodes.get_resources():
            if isinstance(fs_node, File):
                file_paths.append(fs_node.path)
            elif isinstance(fs_node, Folder):
                files = fs_node.list_all_file_paths()
                file_paths.extend(files)
            else:
                self.log_error_message(f"Resource {fs_node.name} is not a file or a folder")

        progress = 0
        error_files: List[str] = []

        for file_path in file_paths:
            try:
                response = ragflow_service.upload_documents(
                    [file_path],
                    params.get_value('dataset_id')
                )
                if response.code != 0:
                    raise Exception(f"RagFlow API error: {response.message}")

                # Start parsing the document if upload was successful
                if response.data:
                    documents_ids = [x.id for x in response.data]
                    ragflow_service.parse_documents(params.get_value('dataset_id'), documents_ids)

            except Exception as e:
                self.log_error_message(f"Error while sending file '{file_path}' to RagFlow Dataset: {str(e)}")
                error_files.append(file_path)

            progress += 1
            self.update_progress_value(progress / len(file_paths) * 100,
                                       f"File {file_path} sent")

        if error_files:
            raise Exception(f"Error while sending files to RagFlow Dataset: {error_files}")

        return {}
