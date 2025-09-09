import io
import os
import uuid
from typing import List, Optional, Union

from openai import OpenAI
from PIL import Image

# Constants
USER_INPUT = "Can you generate a scatter plot with the column 'one' as x and column 'two' as y ? "
FILE_ID = "file-GJk8p3uiMbABZgjTyj4nk2"  # Replace with actual OpenAI file ID
INSTRUCTIONS = f"""You are an expert document analyst. Analyze the provided file and give detailed insights about:
1. Document type and structure
2. Key findings and important information
3. Data quality and completeness
4. Recommendations for further analysis.

File : {FILE_ID}"""
MODEL = "gpt-4o"
TEMPERATURE = 0.1

events = []


class ChatMessage:
    """Simple ChatMessage class for response conversion"""

    def __init__(
            self, role: str, message_type: str, content: str, message_id: str = None, data: Optional[Image.Image] = None):
        self.role = role
        self.type = message_type
        self.content = content
        self.id = message_id or str(uuid.uuid4())
        self.sources: List = []
        self.data = data


def extract_file_from_response(file_id: str, filename: str, client: OpenAI,
                               container_id: Optional[str] = None) -> Union[ChatMessage]:
    """Extract file from OpenAI response - handles images and other files"""

    file_data_binary = None

    try:
        if file_id.startswith('cfile_') and container_id:
            # Container file - use containers API
            file_data_binary = client.containers.files.content.retrieve(file_id, container_id=container_id)
        else:
            # Regular file - use files API
            file_data_binary = client.files.content(file_id)

        # Check file extension to determine handling
        file_extension = os.path.splitext(filename)[1].lower()

        # Handle image files
        if file_extension in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']:
            image_data = Image.open(io.BytesIO(file_data_binary.content))
            return ChatMessage(
                role="assistant",
                message_type="image",
                content=f"Generated image: {filename}",
                data=image_data
            )
        else:
            # Handle other file types as text messages
            return ChatMessage(
                role="assistant",
                message_type="text",
                content=f"📄 File '{filename}' has been generated."
            )

    except Exception as e:
        print(f"Error downloading file {file_id}: {str(e)}")
        raise ValueError(f"Error downloading file {file_id}: {str(e)}")


def stream_conversation_with_file(api_key: Optional[str] = None) -> List[ChatMessage]:
    """
    Stream a conversation with file analysis using OpenAI response.stream

    Args:
        api_key: OpenAI API key (if not provided, uses OPENAI_API_KEY env var)

    Returns:
        List of ChatMessage objects from the streaming response
    """
    messages = []
    current_message_content = ""

    try:
        # Initialize OpenAI client
        client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

        # Create streaming response with file
        with client.responses.stream(
            model=MODEL,
            instructions=INSTRUCTIONS,
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": USER_INPUT},
                ]
            }],
            temperature=TEMPERATURE,
            tools=[{"type": "code_interpreter", "container": {"type": "auto", "file_ids": [FILE_ID]}}]

        ) as stream:

            # Process streaming events
            for event in stream:
                events.append(event)
                print(f"Event type: {event.type}")

                if event.type == "response.output_text.delta":
                    # Accumulate text content
                    current_message_content += event.delta
                    print(f"Text delta: {event.delta}")

                elif event.type == "response.code_interpreter_call_code.delta":
                    # Handle code content
                    code_content = event.delta
                    code_message = ChatMessage(
                        role="assistant",
                        message_type="code",
                        content=code_content
                    )
                    messages.append(code_message)
                    print(f"Code delta: {code_content}")
                elif event.type == "response.output_text.annotation.added":
                    # Handle annotations (like file references)
                    annotation = event.annotation
                    print(f"Annotation added: {annotation}")

                    # Extract file from annotation if it contains file information
                    if isinstance(annotation, dict) and 'file_id' in annotation and 'filename' in annotation:
                        try:
                            file_message = extract_file_from_response(
                                annotation['file_id'],
                                annotation['filename'],
                                client,
                                container_id=annotation.get('container_id')
                            )
                            messages.append(file_message)

                        except (OSError, ValueError) as e:
                            print(f"Error loading file: {str(e)}")
                            error_message = ChatMessage(
                                role="assistant",
                                message_type="text",
                                content=f"[Error loading file: {str(e)}]"
                            )
                            messages.append(error_message)
                        except Exception as e:
                            print(f"Unexpected error loading file: {str(e)}")
                            error_message = ChatMessage(
                                role="assistant",
                                message_type="text",
                                content=f"[Unexpected error loading file: {str(e)}]"
                            )
                            messages.append(error_message)

                elif event.type == "response.output_item.done":
                    # Finalize current message when output item is done
                    if current_message_content.strip():
                        text_message = ChatMessage(
                            role="assistant",
                            message_type="text",
                            content=current_message_content.strip()
                        )
                        messages.append(text_message)
                        current_message_content = ""

                elif event.type == "response.created":
                    # Save response ID for conversation continuity
                    if hasattr(event, 'response') and hasattr(event.response, 'id'):
                        print(f"Response created with ID: {event.response.id}")

            # Get final response
            final_response = stream.get_final_response()
            if final_response:
                print(f"Final response ID: {final_response.id}")

    except Exception as e:
        error_message = ChatMessage(
            role="assistant",
            message_type="text",
            content=f"Error in streaming conversation: {str(e)}"
        )
        messages.append(error_message)

    return messages


def print_chat_messages(messages: List[ChatMessage]):
    """Print chat messages in a formatted way"""
    print("\n" + "="*50)
    print("CONVERSATION MESSAGES")
    print("="*50)

    for i, msg in enumerate(messages, 1):
        print(f"\n[{i}] {msg.role.upper()} ({msg.type}):")
        print(f"ID: {msg.id}")
        print(f"Content: {msg.content}")

        if msg.type == "image" and msg.data:
            print(f"Image Size: {msg.data.size}")
            print(f"Image Mode: {msg.data.mode}")
            # Optionally save the image to disk
            try:
                image_filename = f"extracted_image_{i}_{msg.id[:8]}.png"
                msg.data.save(image_filename)
                print(f"Image saved as: {image_filename}")
            except Exception as e:
                print(f"Could not save image: {e}")

        if msg.sources:
            print(f"Sources: {len(msg.sources)} sources")


def test_streaming_conversation():
    """
    Test function to demonstrate streaming conversation with file
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable is not set")
        return

    print(f"=== Starting Streaming Conversation ===")
    print(f"File ID: {FILE_ID}")
    print(f"Model: {MODEL}")
    print(f"User Input: {USER_INPUT}")
    print(f"Instructions: {INSTRUCTIONS}")

    messages = stream_conversation_with_file(api_key)
    print_chat_messages(messages)


def filter_event_with_annotations(events):
    """Filter events to only those with annotations"""
    return [event for event in events if hasattr(event, 'annotation')]


if __name__ == "__main__":
    test_streaming_conversation()
    print(f"\nTotal events processed: {len(events)}")
