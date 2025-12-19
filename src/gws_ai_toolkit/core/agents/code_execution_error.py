class CodeExecutionError(Exception):
    """Exception raised when generated code execution fails.

    Contains both a user-friendly message and the full stack trace for AI context.
    """

    message: str
    stack_trace: str

    def __init__(self, message: str, stack_trace: str):
        super().__init__(message)
        self.message = message
        self.stack_trace = stack_trace
