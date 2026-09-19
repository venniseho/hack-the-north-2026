import asyncio
import os
from typing import cast

from dotenv import load_dotenv
from backboard import BackboardClient
from backboard.models import ChatMessagesResponse

load_dotenv()

async def main():
    client = BackboardClient(api_key=os.environ["BACKBOARD_API_KEY"])

    # Send a message — thread and assistant are auto-created
    # cast: stream=False (the default) always returns ChatMessagesResponse, never the streaming iterator
    response = cast(ChatMessagesResponse, await client.send_message(
        "Hello! I'm excited to get started.",
        memory="Auto",
    ))
    print(response.content)

    # Continue the conversation using the returned thread_id
    response = cast(ChatMessagesResponse, await client.send_message(
        "What can you help me with?",
        thread_id=response.thread_id,
    ))
    print(response.content)

asyncio.run(main())