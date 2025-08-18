from fastapi import HTTPException
from src.webui.components.browser_use_agent_tab import run_agent_task

manager = None

def set_websocket_manager(ws_manager):
    global manager
    manager = ws_manager

async def run_agent_work(query, url, user):
    try:
        print("\n DELETING THE AGENT EXECUTION JSON FILE")
        with open("src/outputdata/agent_execution.json", "w") as file:
            file.write("")

        async def message_callback(message: str):
            if manager:
                await manager.send_message(message)

        await run_agent_task(query, url, message_callback=message_callback)

        with open("src/outputdata/agent_execution.json", "r") as file:
            data = file.read()

            if data:
                print("data found in the agent_execution.json file")
                print(data)
                return data
            else:
                print("No data found in the agent_execution.json file")
                return {"message": "no data found"}

    except Exception as e:
        print(f"❌ Agent error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

