from typing import AsyncGenerator, Awaitable, Callable, Dict, Any
import asyncio
import json
import logging
import os
import uuid
from src.models import AIModel
from typing import Any, AsyncGenerator, Dict, Optional
import os, time
from browser_use.agent.views import (
    ActionResult,
    AgentHistory,
    AgentHistoryList,
    AgentStepInfo,
    ToolCallingMethod,
)
import re
import ast
import gradio as gr

import re


from browser_use.agent.service import Agent
from browser_use.agent.views import (
    AgentHistoryList,
    AgentOutput,
)
from browser_use.browser.browser import BrowserConfig
from browser_use.browser.context import BrowserContext, BrowserContextConfig
from browser_use.browser.views import BrowserState
from gradio.components import Component
from langchain_core.language_models.chat_models import BaseChatModel

from src.agent.browser_use.browser_use_agent import BrowserUseAgent
from src.browser.custom_browser import CustomBrowser
from src.controller.custom_controller import CustomController
from src.utils import llm_provider
from src.webui.webui_manager import WebuiManager
from src.agent.orchestrator.agent_orchestrator import AgentOrchestrator
import base64
import os
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

import re
import ast

import re



# --- Helper Functions --- (Defined at module level)


async def _initialize_llm(
        provider: Optional[str],
        model_name: Optional[str],
        temperature: float,
        #base_url: Optional[str],              #Not required by current llm_provider implementation
        api_key: Optional[str],
        #num_ctx: Optional[int] = None,        #Context window control not implemented 
) -> Optional[BaseChatModel]:
    """Initializes the LLM based on settings. Returns None if provider/model is missing."""
    if not provider or not model_name:
        logger.info("LLM Provider or Model Name not specified, LLM will be None.")
        return None
    try:
        # Use your actual LLM provider logic here
        logger.info(
            f"Initializing LLM: Provider={provider}, Model={model_name}, Temp={temperature}"
        )
        # Example using a placeholder function
        llm = llm_provider.get_llm_model(
            provider=provider,
            model_name=model_name,
            temperature=temperature,
            #base_url=base_url or None,             #not needed in current setup.
            api_key=api_key or None,
            # Add other relevant params like num_ctx for ollama
            #num_ctx=num_ctx if provider == "ollama" else None,             #may control context window size for some providers but unused here.
        )
        return llm
    except Exception as e:
        logger.error(f"Failed to initialize LLM: {e}", exc_info=True)
        gr.Warning(
            f"Failed to initialize LLM '{model_name}' for provider '{provider}'. Please check settings. Error: {e}"
        )
        return None

#This function is defined to get Gradio settings but is never used anywhere in the code.

# def _get_config_value(
#         webui_manager: WebuiManager,
#         comp_dict: Dict[gr.components.Component, Any],
#         comp_id_suffix: str,
#         default: Any = None,
# ) -> Any:
#     """Safely get value from component dictionary using its ID suffix relative to the tab."""
#     # Assumes component ID format is "tab_name.comp_name"
#     tab_name = "browser_use_agent"  # Hardcode or derive if needed
#     comp_id = f"{tab_name}.{comp_id_suffix}"
#     # Need to find the component object first using the ID from the manager
#     try:
#         comp = webui_manager.get_component_by_id(comp_id)
#         return comp_dict.get(comp, default)
#     except KeyError:
#         # Try accessing settings tabs as well
#         for prefix in ["agent_settings", "browser_settings"]:
#             try:
#                 comp_id = f"{prefix}.{comp_id_suffix}"
#                 comp = webui_manager.get_component_by_id(comp_id)
#                 return comp_dict.get(comp, default)
#             except KeyError:
#                 continue
#         logger.warning(
#             f"Component with suffix '{comp_id_suffix}' not found in manager for value lookup."
#         )
#         return default


# def _format_agent_output(model_output: AgentOutput) -> str:
#     """Formats AgentOutput for display in the chatbot using JSON."""
#     content = ""
#     if model_output:
#         try:
#             # Directly use model_dump if actions and current_state are Pydantic models
#             action_dump = [
#                 action.model_dump(exclude_none=True) for action in model_output.action
#             ]

#             state_dump = model_output.current_state.model_dump(exclude_none=True)
#             model_output_dump = {
#                 "current_state": state_dump,
#                 "action": action_dump,
#             }
#             # Dump to JSON string with indentation
#             json_string = json.dumps(model_output_dump, indent=4, ensure_ascii=False)
#             # Wrap in <pre><code> for proper display in HTML
#             content = f"<pre><code class='language-json'>{json_string}</code></pre>"

#         except AttributeError as ae:
#             logger.error(
#                 f"AttributeError during model dump: {ae}. Check if 'action' or 'current_state' or their items support 'model_dump'."
#             )
#             content = f"<pre><code>Error: Could not format agent output (AttributeError: {ae}).\nRaw output: {str(model_output)}</code></pre>"
#         except Exception as e:
#             logger.error(f"Error formatting agent output: {e}", exc_info=True)
#             # Fallback to simple string representation on error
#             content = f"<pre><code>Error formatting agent output.\nRaw output:\n{str(model_output)}</code></pre>"

#     return content.strip()


# --- Updated Callback Implementation ---


# async def _handle_new_step(
#         webui_manager: WebuiManager, state: BrowserState, output: AgentOutput, step_num: int
# ):
#     """Callback for each step taken by the agent, including screenshot display."""

#     # print("\n\n\n\n\n HANDLE NEW STEP CALLED\n\n\n\n\n")

#     # Use the correct chat history attribute name from the user's code
#     if not hasattr(webui_manager, "bu_chat_history"):
#         logger.error(
#             "Attribute 'bu_chat_history' not found in webui_manager! Cannot add chat message."
#         )
#         # Initialize it maybe? Or raise an error? For now, log and potentially skip chat update.
#         webui_manager.bu_chat_history = []  # Initialize if missing (consider if this is the right place)
#         # return # Or stop if this is critical
#     step_num -= 1
#     logger.info(f"Step {step_num} completed.")

#     #get the current directory
#     #and create a new directory according to the step number
#     current_dir = os.path.dirname(__file__)
    #     # Paths for local development
    #     # output_data_dir = os.path.join(current_dir, "..", "..", "src", "outputdata", "step_" + str(step_num))
    #     #output_data_dir = os.path.join(current_dir, "..", "..", "outputdata", "step_" + str(step_num))
    #     # output_data_dir = "./outputdata"
    #     
    #     # Paths for Dockerized application
    #     output_data_dir = "/app/src/outputdata"

#     os.makedirs(output_data_dir, exist_ok=True)

#     # --- Screenshot Handling ---
#     screenshot_html = ""
#     # Ensure state.screenshot exists and is not empty before proceeding
#     # Use getattr for safer access
#     screenshot_data = getattr(state, "screenshot", None)
#     # print("\n\n\n\n\n SCREENSHOT DATA: ", screenshot_data, "\n\n\n\n\n")
#     if screenshot_data:
#         try:
#             # Basic validation: check if it looks like base64
#             if (
#                     isinstance(screenshot_data, str) and len(screenshot_data) > 100
#             ):  
#                 # Decode the base64 string
#                 #image_to_save_locally = screenshot_data = base64.b64decode(screenshot_data)      # change this line of code bc here screenshot_data value is override
#                 image_to_save_locally = base64.b64decode(screenshot_data)

#                 #saving the image in the output data directory
#                 image_path = os.path.join(output_data_dir, "output_image.png")
#                 try:
#                     logger.info(f"Saving image to {image_path}")
#                     with open(image_path, "wb") as f:
#                         f.write(image_to_save_locally)
#                     logger.info(f"\n IMAGE SAVED TO PATH: {image_path}")
#                 except Exception as e:
#                     logger.error(f"Error saving image: {e}")                
                
#                 # Arbitrary length check
#                 # *** UPDATED STYLE: Removed centering, adjusted width ***
#                 img_tag = f'<img src="data:image/jpeg;base64,{image_to_save_locally}" alt="Step {step_num} Screenshot" style="max-width: 800px; max-height: 600px; object-fit:contain;" />'
#                 screenshot_html = (
#                         img_tag + "<br/>"
#                 )  # Use <br/> for line break after inline-block image
#             else:
#                 logger.warning(
#                     f"Screenshot for step {step_num} seems invalid (type: {type(screenshot_data)}, len: {len(screenshot_data) if isinstance(screenshot_data, str) else 'N/A'})."
#                 )
#                 screenshot_html = "**[Invalid screenshot data]**<br/>"

#         except Exception as e:
#             logger.error(
#                 f"Error processing or formatting screenshot for step {step_num}: {e}",
#                 exc_info=True,
#             )
#             screenshot_html = "**[Error displaying screenshot]**<br/>"
#     else:
#         logger.debug(f"No screenshot available for step {step_num}.")

#     # --- Format Agent Output ---
#     formatted_output = _format_agent_output(output)  # Use the updated function

#     # --- Combine and Append to Chat ---
#     step_header = f"--- **Step {step_num}** ---"
#     # Combine header, image (with line break), and JSON block
#     final_content = step_header + "<br/>" + screenshot_html + formatted_output
#     save_chat = {
#         "evaluation_previous_goal": getattr(output.current_state, "evaluation_previous_goal", ""),
#         "memory": getattr(output.current_state, "memory", ""),
#         "next_goal": getattr(output.current_state, "next_goal", ""),
#     }

#     chat_message = {
#         "role": "assistant",
#         "content": final_content.strip(),  # Remove leading/trailing whitespace
#     }

#     #lets store the formatted output in a file
#     agent_response_path = os.path.join(output_data_dir, "agent_response.json")
#     try:
#         logger.info(f"Saving agent response to {agent_response_path}")
#         with open(agent_response_path, "w") as f:
#             json.dump(save_chat, f)
#             logger.info(f"\n AGENT RESPONSE SAVED TO PATH: {agent_response_path}")
#     except Exception as e:
#         logger.error(f"Error saving agent response: {e}")


#     # Append to the correct chat history list
#     webui_manager.bu_chat_history.append(chat_message)
        
#     await asyncio.sleep(0.05)

#     # Check if video recording is active
#     if hasattr(webui_manager.bu_browser, ''
#     ''):
#         if webui_manager.bu_browser.recorder.is_video_recording():
#             logger.info("🎥 Video recording is active")
#         else:
#             logger.warning("⚠️ Video recording is not active!")


# def _handle_done(webui_manager: WebuiManager, history: AgentHistoryList):
#     """Callback when the agent finishes the task (success or failure)."""
#     logger.info(
#         f"Agent task finished. Duration: {history.total_duration_seconds():.2f}s, Tokens: {history.total_input_tokens()}"
#     )
#     final_summary = "**Task Completed**\n"
#     final_summary += f"- Duration: {history.total_duration_seconds():.2f} seconds\n"
#     final_summary += f"- Total Input Tokens: {history.total_input_tokens()}\n"  # Or total tokens if available

#     final_result = history.final_result()
#     if final_result:
#         final_summary += f"- Final Result: {final_result}\n"

#     errors = history.errors()
#     if errors and any(errors):
#         final_summary += f"- **Errors:**\n```\n{errors}\n```\n"
#     else:
#         final_summary += "- Status: Success\n"

#     webui_manager.bu_chat_history.append(
#         {"role": "assistant", "content": final_summary}
#     )

#This callback handles agent help requests but isn’t used in the current flow. 
# and This feature is disabled for the current use case.

# async def _ask_assistant_callback(
#         webui_manager: WebuiManager, query: str #, browser_context: BrowserContext
# ) -> Dict[str, Any]:
#     """Callback triggered by the agent's ask_for_assistant action."""
#     logger.info("Agent requires assistance. Waiting for user input.")

#     if not hasattr(webui_manager, "_chat_history"):
#         logger.error("Chat history not found in webui_manager during ask_assistant!")
#         return {"response": "Internal Error: Cannot display help request."}

#     webui_manager.bu_chat_history.append(
#         {
#             "role": "assistant",
#             "content": f"**Need Help:** {query}\nPlease provide information or perform the required action in the browser, then type your response/confirmation below and click 'Submit Response'.",
#         }
#     )

#     # Use state stored in webui_manager
#     webui_manager.bu_response_event = asyncio.Event()
#     webui_manager.bu_user_help_response = None  # Reset previous response

#     try:
#         logger.info("Waiting for user response event...")
#         await asyncio.wait_for(
#             webui_manager.bu_response_event.wait(), timeout=3600.0
#         )  # Long timeout
#         logger.info("User response event received.")
#     except asyncio.TimeoutError:
#         logger.warning("Timeout waiting for user assistance.")
#         webui_manager.bu_chat_history.append(
#             {
#                 "role": "assistant",
#                 "content": "**Timeout:** No response received. Trying to proceed.",
#             }
#         )
#         webui_manager.bu_response_event = None  # Clear the event
#         return {"response": "Timeout: User did not respond."}  # Inform the agent

#     response = webui_manager.bu_user_help_response
#     webui_manager.bu_chat_history.append(
#         {"role": "user", "content": response}
#     )  # Show user response in chat
#     webui_manager.bu_response_event = (
#         None  # Clear the event for the next potential request
#     )
#     return {"response": response}

# --- Core Agent Execution Logic --- (Needs access to webui_manager)

async def run_agent_task(query: str, url: str, message_callback: Optional[Callable[[str], Awaitable[None]]] = None) -> Dict[str, Any]:
    """
    Simplified agent runner that handles everything
    Returns: {
        "task_id": str,
        "final_result": str
    }
    """
    task_id = str(uuid.uuid4())
    if message_callback:
        await message_callback(f"Task ID: {task_id}")

    
    output_dir = os.path.join("/app", "src", "outputdata")
    os.makedirs(output_dir, exist_ok=True)

    if not os.getenv("DISPLAY"):
        os.environ["DISPLAY"] = ":99"

    if message_callback:
        
        await message_callback(f"🖥️ Using display: {os.environ['DISPLAY']}")

    print(f"🖥️ Using display: {os.getenv('DISPLAY')}")
    
    
    # 1. Initialize browser
    playwright = await async_playwright().start()
    browser = CustomBrowser(
        config=BrowserConfig(
            headless=False,
            disable_security=False,
            fullscreen=True,
            extra_browser_args=[
                "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
                "--disable-web-security", "--disable-features=VizDisplayCompositor",
                "--start-maximized", "--window-size=1920,1080", "--window-position=0,0",
                "--disable-extensions", "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows", "--disable-renderer-backgrounding",
                "--force-device-scale-factor=1", "--high-dpi-support=1"
            ],
            new_context_config=BrowserContextConfig(window_width=1920, window_height=1080)
        )
    )

    playwright_browser = await browser._setup_builtin_browser(playwright)
    # Recording per tab/context is handled by CustomBrowserContext

    context_config = BrowserContextConfig(
        save_downloads_path=os.path.join(output_dir, "downloads"),
        window_height=1080,
        window_width=1920,
    )
    browser_context = await browser.new_context(config=context_config)
    await browser_context.setup()

    if message_callback:
        await message_callback("🌐 Maximizing browser window...")

    try:
        # Use the primary session page instead of creating/closing a helper tab,
        # so the first navigation can be migrated and recorded as tab_001
        session = await browser_context.get_session()
        page = session.context.pages[0] if session.context.pages else await session.context.new_page()
        await page.set_viewport_size({"width": 1920, "height": 1080})
        await page.evaluate("""
            if (window.screen && window.screen.availWidth && window.screen.availHeight) {
                window.resizeTo(window.screen.availWidth, window.screen.availHeight);
                window.moveTo(0, 0);
            }
            setTimeout(() => {
                if (document.documentElement.requestFullscreen) {
                    document.documentElement.requestFullscreen();
                } else if (document.documentElement.webkitRequestFullscreen) {
                    document.documentElement.webkitRequestFullscreen();
                } else if (document.documentElement.msRequestFullscreen) {
                    document.documentElement.msRequestFullscreen();
                }
            }, 1000);
            if (window.chrome && window.chrome.webstore) {
                window.resizeTo(screen.availWidth, screen.availHeight);
            }
        """)
        # Do not close the page; the agent will navigate this page first
    except Exception as e:
        print(f"⚠️ Could not maximize browser window: {e}")

    # 3. Initialize controller
    controller = CustomController()

    if message_callback:
        await message_callback("🧠 Initializing LLM...")

    llm = await _initialize_llm(
        provider="openai",
        model_name=AIModel.GPT_4O.value,
        temperature=0.6,
        api_key=os.getenv("OPENAI_API_KEY"),
         message_callback=message_callback
    )
    
    # 4. Step handler with WebSocket message sending
    async def handle_step(state: BrowserState, output: AgentOutput, step_num: int):
        step_dir = os.path.join(output_dir, f"step_{step_num}")
        os.makedirs(step_dir, exist_ok=True)


        evaluation = getattr(output.current_state, "evaluation_previous_goal", "")
        memory = getattr(output.current_state, "memory", "")
        next_goal = getattr(output.current_state, "next_goal", "")
        actions = output.actions_taken if hasattr(output, "actions_taken") else []
        if message_callback:
            await message_callback("----------------------------")
            await message_callback(f"🤖 Step {step_num}: Running step...")

            if evaluation:
                await message_callback(f" ⚠ Eval: {evaluation}")
            if memory:
                await message_callback(f"🧠 Memory: {memory}")
            if next_goal:
                await message_callback(f"🎯 Next goal: {next_goal}")
            

        response_data = {
            "evaluation_previous_goal": getattr(output.current_state, "evaluation_previous_goal", ""),
            "memory": getattr(output.current_state, "memory", ""),
            "next_goal": getattr(output.current_state, "next_goal", ""),
        }

        # if message_callback:
            
        #     await message_callback(f"🤖 Step {step_num}: {response_data['next_goal']}")

        response_path = os.path.join(step_dir, "agent_response.json")
        with open(response_path, "w") as f:
            json.dump(response_data, f)

        return None, response_path

    if message_callback:
        await message_callback("🚀 Starting agent...")

    # 5. Run agent
    agent = AgentOrchestrator(
        llm=llm,
        browser_config={
            "headless": False,
            "window_width": 1920,
            "window_height": 1080,
            "use_own_browser": True,
            "disable_security": False,
            "url": url
        },
        use_vision=True,
        max_actions_per_step=5,
        generate_gif=False,
        user_query=query,
        url=url,
        register_new_step_callback=handle_step,
        override_system_prompt=None,
        extend_system_prompt=None,
        message_callback=message_callback
    )

    history = await agent.run(
        task=f"{query}  url: {url}",
        browser=browser,
        browser_context=browser_context,
        controller=controller
    )

    last_result = None
    if history.history:
        last_item = history.history[-1]
        if last_item.result:
            last_result = last_item.result[-1]

    if last_result:
        print("✅ Extracted Content:", last_result.extracted_content)
        print("✅ Is Done:", last_result.is_done)
    else:
        print("⚠️ No result found.")

    # if message_callback:
    #     await message_callback("📦 Processing final result...")

    # Recordings are saved/closed by CustomBrowserContext.close()

    await browser_context.close()
    await browser.close()
    await playwright.stop()

    final_result = "No result"
    if last_result and last_result.extracted_content:
        content = last_result.extracted_content
        match = re.search(r"'done':\s*\{(.*?)\}", content, re.DOTALL)
        if match:
            final_result = match.group(1).strip()
        else:
            final_result = content.strip()
    else:
        final_result = history.final_result() or "No result"
    
    if message_callback:
        await message_callback("----------------------------")
        await message_callback(f"✅ Task Complete: {final_result}")

    return {
        "task_id": task_id,
        "final_result": final_result
    }

    
    
async def _initialize_llm(
        provider: str,
        model_name: str,
        temperature: float,
        api_key: Optional[str] = None,
        message_callback: Optional[Callable[[str], Awaitable[None]]] = None
) -> BaseChatModel:
    """Initialize LLM instance"""
    logger.info(f"Initializing LLM: {provider}/{model_name}")
    if message_callback:
        await message_callback(f"Initializing LLM: {provider}/{model_name}")  # Send to WebSocket

    return llm_provider.get_llm_model(
        provider=provider,
        model_name=model_name,
        temperature=temperature,
        api_key=api_key,
    )

# changed####******!!!!!!
# async def run_agent_task(
#         webui_manager: WebuiManager, components: Dict[gr.components.Component, Any]
# ) -> AsyncGenerator[Dict[gr.components.Component, Any], None]:
    
#     # Initialize final_update at the start
#     final_update = {}

#     # --- Get Components ---
#     # Need handles to specific UI components to update them
#     user_input_comp = webui_manager.get_component_by_id("browser_use_agent.user_input")
#     url_input_comp = webui_manager.get_component_by_id("browser_use_agent.url_input")
#     run_button_comp = webui_manager.get_component_by_id("browser_use_agent.run_button")
#     stop_button_comp = webui_manager.get_component_by_id("browser_use_agent.stop_button")
#     #pause_resume_button_comp = webui_manager.get_component_by_id("browser_use_agent.pause_resume_button")      #Pause/resume functionality not implemented in agent state machine
#     clear_button_comp = webui_manager.get_component_by_id("browser_use_agent.clear_button")
#     #chatbot_comp = webui_manager.get_component_by_id("browser_use_agent.chatbot")
#     history_file_comp = webui_manager.get_component_by_id("browser_use_agent.agent_history_file")
#     gif_comp = webui_manager.get_component_by_id("browser_use_agent.recording_gif")
#     #browser_view_comp = webui_manager.get_component_by_id("browser_use_agent.browser_view")                    #not used used anywhere

#     # --- 1. Get Task and Initial UI Update ---
#     task = components.get(user_input_comp, "").strip()
#     url = components.get(url_input_comp, "").strip()

#     #lets always make sure that if the task is not empty then it should have the url in it
#     if task:
#         task += f"  url:  {url}"

#     else:
#         gr.Warning("Please enter a task.")
#         yield {run_button_comp: gr.update(interactive=True)}
#         return

#     # Set running state indirectly via _current_task
#     webui_manager.bu_chat_history.append({"role": "user", "content": task})

#     yield {
#         user_input_comp: gr.Textbox(
#             value="", interactive=False, placeholder="Agent is running..."
#         ),
#         run_button_comp: gr.Button(value="⏳ Running...", interactive=False),
#         stop_button_comp: gr.Button(interactive=True),
#         #pause_resume_button_comp: gr.Button(value="⏸️ Pause", interactive=True),                 #resume and pause button is not needed
#         clear_button_comp: gr.Button(interactive=False),
#         #chatbot_comp: gr.update(value=webui_manager.bu_chat_history),
#         history_file_comp: gr.update(value=None),
#         gif_comp: gr.update(value=None),
#     }

#     # --- 2. Get Settings ---
#     def get_setting(key, default=None):
#         comp = webui_manager.id_to_component.get(f"agent_settings.{key}")
#         return components.get(comp, default) if comp else default

#     # Main LLM Settings
#     llm_provider_name = get_setting("llm_provider") or "openai"
#     llm_model_name = get_setting("llm_model_name") or "gpt-4o"
#     llm_temperature = 0.6 #get_setting("llm_temperature", 0.6)         #we are not giving option to user to select the temp
#     #llm_base_url = get_setting("llm_base_url") or None                #no need for this here
#     llm_api_key =None #get_setting("llm_api_key") or None
#     #ollama_num_ctx = get_setting("ollama_num_ctx", 16000)              #ontext window setting is not used in current LLM initialization or agent workflow
#     use_vision = True #get_setting("use_vision", True)
#     max_actions = 5 # get_setting("max_actions_per_step", 5)
#     #max_steps = get_setting("max_steps", 25)
#     #tool_calling_method = get_setting("tool_calling_method", "auto")    # Not implemented in agent workflow
#     #max_input_tokens = get_setting("max_input_tokens", 16000)
#     # override_system_prompt = get_setting("override_system_prompt") or None
#     # extend_system_prompt = get_setting("extend_system_prompt") or None

#     #we would not be using the override_system_prompt and extend_system_prompt
#     # as they are being passed to the AgentOrhcestrator, we need to srt a default value
#     override_system_prompt = None
#     extend_system_prompt = None

#     # --- 3. Initialize LLM ---
#     logger.info(f"Initializing LLM: Provider={llm_provider_name}, Model={llm_model_name}, Temp={llm_temperature}")
#     main_llm = await _initialize_llm(
#         llm_provider_name,
#         llm_model_name,
#         llm_temperature,
#         #llm_base_url,
#         llm_api_key,
#         #ollama_num_ctx if llm_provider_name == "ollama" else None,
#     )


# #planner functionality using a separate LLM is not required in the current setup.


#     # planner_llm_provider_name = None                        
#     # planner_llm = None
#     # planner_use_vision = False
#     # if planner_llm_provider_name:
#     #     planner_llm_model_name = None# get_setting("planner_llm_model_name")
#     #     planner_llm_temperature = 0.6 #get_setting("planner_llm_temperature", 0.6)
#     #     #planner_ollama_num_ctx = get_setting("planner_ollama_num_ctx", 16000)
#     #     #planner_llm_base_url = get_setting("planner_llm_base_url") or None
#     #     #planner_llm_api_key = get_setting("planner_llm_api_key") or None
#     #     planner_use_vision = get_setting("planner_use_vision", False)



#     #     planner_llm = await _initialize_llm(
#     #         planner_llm_provider_name,
#     #         planner_llm_model_name,
#     #         planner_llm_temperature,
#     #         #planner_llm_base_url,
#     #         #planner_llm_api_key,
#     #         #planner_ollama_num_ctx if planner_llm_provider_name == "ollama" else None,
#     #     )

#     # --- 4. Browser Settings ---
#     def get_browser_setting(key, default=None):
#         comp = webui_manager.id_to_component.get(f"browser_settings.{key}")
#         return components.get(comp, default) if comp else default

#     #browser_binary_path = get_browser_setting("browser_binary_path") or None               #not needed
#     #browser_user_data_dir = get_browser_setting("browser_user_data_dir") or None          #not accessed any where
#     use_own_browser = True # get_browser_setting("use_own_browser", True)                  #we are not giving this option to the user
#     keep_browser_open = False #get_browser_setting("keep_browser_open", False)
#     headless = False #get_browser_setting("headless", False)                                #setting the value False bydefault
#     disable_security = False# get_browser_setting("disable_security", False)
#     window_w = 1280 #int(get_browser_setting("window_w", 1280))                             #no need to get value from user hardcode it
#     window_h = 1100#int(get_browser_setting("window_h", 1100))                              #no need to get value from user hardcode it
#     #cdp_url = get_browser_setting("cdp_url") or None                                  # not required in current browser
#     #wss_url = get_browser_setting("wss_url") or None                                   #not used in this deployment.
#     save_recording_path = None #get_browser_setting("save_recording_path") or None         # Recording handled through context config
#     save_trace_path = None #get_browser_setting("save_trace_path") or None                 # Tracing handled through context config
    #     # Paths for local development
    #     # save_agent_history_path = get_browser_setting("save_agent_history_path", "./tmp/agent_history")
    #     # save_download_path = get_browser_setting("save_download_path", "./tmp/downloads")
    #     
    #     # Paths for Dockerized application
    #     save_agent_history_path = get_browser_setting("save_agent_history_path", "/app/src/outputdata/agent_history")
    #     save_download_path = get_browser_setting("save_download_path", "/app/src/outputdata/downloads")
#     #should_close_browser_on_finish = not keep_browser_open                                #this logic is not used here 

#     # Create necessary directories
#     os.makedirs(save_agent_history_path, exist_ok=True)
#     if save_recording_path:
#         os.makedirs(save_recording_path, exist_ok=True)
#     if save_trace_path:
#         os.makedirs(save_trace_path, exist_ok=True)
#     if save_download_path:
#         os.makedirs(save_download_path, exist_ok=True)

#     # --- 5. Initialize Browser and Context ---
#     try:
#         # Close existing resources if not keeping open
#         if not keep_browser_open:
#             if webui_manager.bu_browser_context:
#                 logger.info("Closing previous browser context.")
#                 await webui_manager.bu_browser_context.close()
#                 webui_manager.bu_browser_context = None
#             if webui_manager.bu_browser:
#                 logger.info("Closing previous browser.")
#                 await webui_manager.bu_browser.close()
#                 webui_manager.bu_browser = None

#         # Create Browser if needed
#         if not webui_manager.bu_browser:
#             logger.info("Launching new browser instance.")
#             extra_args = []

#             # if use_own_browser:
#             #     browser_binary_path = os.getenv("BROWSER_PATH", None) or browser_binary_path
#             #     if browser_binary_path == "":
#             #         browser_binary_path = None
#             #     browser_user_data = browser_user_data_dir or os.getenv("BROWSER_USER_DATA", None)
#             #     if browser_user_data:
#             #         extra_args += [f"--user-data-dir={browser_user_data}"]
#             # else:
#             #     browser_binary_path = None

#             webui_manager.bu_browser = CustomBrowser(
#                 config=BrowserConfig(
#                     headless=headless,
#                     disable_security=disable_security,
#                     #browser_binary_path=browser_binary_path,               #no need , already removed from browser settings
#                     extra_browser_args=extra_args,
#                     # wss_url=wss_url,                                       #already removed from browser settings
#                     # cdp_url=cdp_url,                                       #no need,already removed from get browser settings
#                     new_context_config=BrowserContextConfig(
#                         window_width=window_w,
#                         window_height=window_h,
#                     )
#                 )
#             )
            
#             # Initialize the browser and keep playwright instance alive
#             webui_manager.bu_playwright = await async_playwright().start()
#             webui_manager.bu_browser.playwright_browser = await webui_manager.bu_browser._setup_builtin_browser(webui_manager.bu_playwright)

#         # Create Context if needed
#         if not webui_manager.bu_browser_context:
#             logger.info("Creating new browser context.")
#             context_config = BrowserContextConfig(
#                 # Paths for local development
#                 # trace_path=save_trace_path if save_trace_path else None,
#                 # save_recording_path=save_recording_path if save_recording_path else None,
#                 # save_downloads_path=save_download_path if save_download_path else None,
#                 
#                 # Paths for Dockerized application
#                 trace_path=save_trace_path if save_trace_path else None,
#                 save_recording_path=save_recording_path if save_recording_path else None,
#                 save_downloads_path=save_download_path if save_download_path else None,
#                 window_height=window_h,
#                 window_width=window_w,
#             )
#             if not webui_manager.bu_browser:
#                 raise ValueError("Browser not initialized, cannot create context.")
            
#             webui_manager.bu_browser_context = (
#                 await webui_manager.bu_browser.new_context(config=context_config)
#             )

#             print("\n\n\n\n RECORD VIDEO.....................`: \n\n\n\n")
#             logger.info("Setting up browser context with video recording...")
#             await webui_manager.bu_browser_context.setup()
#             logger.info("Browser context setup complete with video recording enabled")

#         # Initialize controller if needed
#         if not webui_manager.bu_controller:
#             webui_manager.bu_controller = CustomController()

#         # --- 6. Initialize or Update Agent Orchestrator ---
#         webui_manager.bu_agent_task_id = str(uuid.uuid4())  # New ID for this task run
#         os.makedirs(
#             os.path.join(save_agent_history_path, webui_manager.bu_agent_task_id),
#             exist_ok=True,
#         )
#         history_file = os.path.join(
#             save_agent_history_path,
#             webui_manager.bu_agent_task_id,
#             f"{webui_manager.bu_agent_task_id}.json",
#         )
#         gif_path = os.path.join(
#             save_agent_history_path,
#             webui_manager.bu_agent_task_id,
#             f"{webui_manager.bu_agent_task_id}.gif",
#         )

#         # Pass the webui_manager to callbacks when wrapping them
#         async def step_callback_wrapper(
#                 state: BrowserState, output: AgentOutput, step_num: int
#         ):
#             # print("\n\n\n\n\n STEP CALLBACK WRAPPER CALLED\n\n\n\n\n")
#             await _handle_new_step(webui_manager, state, output, step_num)

#         def done_callback_wrapper(history: AgentHistoryList):
#             _handle_done(webui_manager, history)

#         if not webui_manager.bu_agent:
#             logger.info(f"Initializing new agent orchestrator for task: {task}")
#             if not webui_manager.bu_browser or not webui_manager.bu_browser_context:
#                 raise ValueError(
#                     "Browser or Context not initialized, cannot create agent."
#                 )
#             webui_manager.bu_agent = AgentOrchestrator(
#                 llm=main_llm,
#                 browser_config={
#                     "headless": headless,
#                     "window_width": window_w,
#                     "window_height": window_h,
#                     "use_own_browser": use_own_browser,
#                     #"browser_binary_path": browser_binary_path,                    #is already removed from LLM initialzation... 
#                     #"wss_url": wss_url,                                            #wss is already removed from LLM initialzation...
#                     #"cdp_url": cdp_url,                                            #same for cdp
#                     "disable_security": disable_security,
#                     "url": url if url else None
#                 },
#                 use_vision=use_vision,
#                 max_actions_per_step=max_actions,
#                 generate_gif=gif_path,
#                 user_query=task,
#                 url=url if url else None,
#                 register_new_step_callback = step_callback_wrapper,
#                 done_callback_wrapper = done_callback_wrapper,
#                 override_system_prompt = override_system_prompt,
#                 extend_system_prompt = extend_system_prompt,
#                 # planner_llm = None,                                                         #only using main LLm for every thing
#                 # use_vision_for_planner = planner_use_vision if planner_llm else False,
                
#             )

#         # --- 7. Run Agent Task and Stream Updates ---
#         agent_run_coro = webui_manager.bu_agent.run(
#             task=task,
#             browser=webui_manager.bu_browser,
#             browser_context=webui_manager.bu_browser_context,
#             controller=webui_manager.bu_controller
#         )
#         agent_task = asyncio.create_task(agent_run_coro)
#         webui_manager.bu_current_task = agent_task

#         # Wait for the agent to complete
#         try:
#             history = await agent_task
#             logger.info("Agent task finished.")
            
#             # Force close browser and save videos
#             if webui_manager.bu_browser_context:
#                 logger.info("Task completed - Saving videos and closing browser...")
#                 try:
#                     # Save videos first
#                     video_paths = await webui_manager.bu_browser_context.save_videos()
#                     if video_paths:
#                         for path in video_paths:
#                             logger.info(f"Video recording saved to: {path}")
#                     else:
#                         logger.warning("No video recordings found to save")
                        
#                     # Force close everything
#                     logger.info("Closing browser context after task.")
#                     await webui_manager.bu_browser_context.close()
#                     webui_manager.bu_browser_context = None
                    
#                     if webui_manager.bu_browser:
#                         logger.info("Closing browser after task.")
#                         await webui_manager.bu_browser.close()
#                         webui_manager.bu_browser = None
                        
#                     if webui_manager.bu_playwright:
#                         logger.info("Closing playwright after task.")
#                         await webui_manager.bu_playwright.stop()
#                         webui_manager.bu_playwright = None
                        
#                 except Exception as e:
#                     logger.error(f"Error during cleanup: {e}")
            
#             # Save history to file
#             with open(history_file, "w") as f:
#                 json.dump(history.dict(), f, indent=2)
#             logger.info(f"Saved agent history to: {history_file}")
            
#             # Initialize final_update at the start
#             final_update = {
#                 #chatbot_comp: gr.update(value=webui_manager.bu_chat_history),
#                 run_button_comp: gr.update(interactive=True),
#                 stop_button_comp: gr.update(interactive=False),
#                 #pause_resume_button_comp: gr.update(interactive=False),                     #noneed for this button
#                 history_file_comp: gr.update(value=history_file),
#             }
            
#             if os.path.exists(gif_path):
#                 final_update[gif_comp] = gr.update(value=gif_path, visible=True)
                
#             yield final_update
            
#         except Exception as e:
#             logger.error(f"Error during agent execution: {e}", exc_info=True)
#             error_message = (
#                 f"**Agent Execution Error:**\n```\n{type(e).__name__}: {e}\n```"
#             )
#             if not any(
#                     error_message in msg.get("content", "")
#                     for msg in webui_manager.bu_chat_history
#                     if msg.get("role") == "assistant"
#             ):
#                 webui_manager.bu_chat_history.append(
#                     {"role": "assistant", "content": error_message}
#                 )
#             #final_update[chatbot_comp] = gr.update(value=webui_manager.bu_chat_history)
#             yield final_update
#             gr.Error(f"Agent execution failed: {e}")

#         finally:
#             # Just clear the current task reference
#             webui_manager.bu_current_task = None

#     except Exception as e:
#         # Catch errors during setup (before agent run starts)
#         logger.error(f"Error setting up agent task: {e}", exc_info=True)
#         webui_manager.bu_current_task = None  # Ensure state is reset
        
#         # Update final_update with error state
#         final_update.update({
#             user_input_comp: gr.update(
#                 interactive=True, placeholder="Error during setup. Enter task..."
#             ),
#             run_button_comp: gr.update(value="▶️ Submit Task", interactive=True),
#             stop_button_comp: gr.update(value="⏹️ Stop", interactive=False),
#             #pause_resume_button_comp: gr.update(value="⏸️ Pause", interactive=False),            #no need right now for this button
#             clear_button_comp: gr.update(interactive=True),
#             # chatbot_comp: gr.update(
#             #     value=webui_manager.bu_chat_history
#             #           + [{"role": "assistant", "content": f"**Setup Error:** {e}"}]
#             # ),
#         })
#         yield final_update


# --- Button Click Handlers --- (Need access to webui_manager)


async def handle_submit(
        webui_manager: WebuiManager, components: Dict[gr.components.Component, Any]
):
    """Handles clicks on the main 'Submit' button."""
    user_input_comp = webui_manager.get_component_by_id("browser_use_agent.user_input")
    user_input_value = components.get(user_input_comp, "").strip()

    # Check if waiting for user assistance
    if webui_manager.bu_response_event and not webui_manager.bu_response_event.is_set():
        logger.info(f"User submitted assistance: {user_input_value}")
        webui_manager.bu_user_help_response = (
            user_input_value if user_input_value else "User provided no text response."
        )
        webui_manager.bu_response_event.set()
        # UI updates handled by the main loop reacting to the event being set
        yield {
            user_input_comp: gr.update(
                value="",
                interactive=False,
                placeholder="Waiting for agent to continue...",
            ),
            webui_manager.get_component_by_id(
                "browser_use_agent.run_button"
            ): gr.update(value="⏳ Running...", interactive=False),
        }
    # Check if a task is currently running (using _current_task)
    elif webui_manager.bu_current_task and not webui_manager.bu_current_task.done():
        logger.warning(
            "Submit button clicked while agent is already running and not asking for help."
        )
        gr.Info("Agent is currently running. Please wait or use Stop/Pause.")
        yield {}  # No change
    else:
        # Handle submission for a new task
        logger.info("Submit button clicked for new task.")
        # Use async generator to stream updates from run_agent_task
        async for update in run_agent_task(webui_manager, components):
            yield update


async def handle_stop(webui_manager: WebuiManager):
    """Handles clicks on the 'Stop' button."""
    logger.info("Stop button clicked.")
    agent = webui_manager.bu_agent
    task = webui_manager.bu_current_task

    if agent and task and not task.done():
        # Signal the agent to stop by setting its internal flag
        agent.state.stopped = True
        agent.state.paused = False  # Ensure not paused if stopped
        return {
            webui_manager.get_component_by_id(
                "browser_use_agent.stop_button"
            ): gr.update(interactive=False, value="⏹️ Stopping...")
            
            #Pause/resume functionality is currently disabled and not handled in the agent workflow.
            
            # ,webui_manager.get_component_by_id(
            #     "browser_use_agent.pause_resume_button"
            # ): gr.update(interactive=False)
            ,
            webui_manager.get_component_by_id(
                "browser_use_agent.run_button"
            ): gr.update(interactive=False),
        }
    else:
        logger.warning("Stop clicked but agent is not running or task is already done.")
        # Reset UI just in case it's stuck
        return {
            webui_manager.get_component_by_id(
                "browser_use_agent.run_button"
            ): gr.update(interactive=True),
            webui_manager.get_component_by_id(
                "browser_use_agent.stop_button"
            ): gr.update(interactive=False),
            
            #Pause/resume functionality is currently disabled and not handled in the agent workflow.

            # webui_manager.get_component_by_id(
            #     "browser_use_agent.pause_resume_button"
            # ): gr.update(interactive=False),
            webui_manager.get_component_by_id(
                "browser_use_agent.clear_button"
            ): gr.update(interactive=True),
        }
    

# Pause/resume functionality not implemented in agent state machine


# async def handle_pause_resume(webui_manager: WebuiManager):
#     """Handles clicks on the 'Pause/Resume' button."""
#     agent = webui_manager.bu_agent
#     task = webui_manager.bu_current_task

#     if agent and task and not task.done():
#         if agent.state.paused:
#             logger.info("Resume button clicked.")
#             agent.resume()
#             # UI update happens in main loop
#             return {
#                 webui_manager.get_component_by_id(
#                     "browser_use_agent.pause_resume_button"
#                 ): gr.update(value="⏸️ Pause", interactive=True)
#             }  # Optimistic update
#         else:
#             logger.info("Pause button clicked.")
#             agent.pause()
#             return {
#                 webui_manager.get_component_by_id(
#                     "browser_use_agent.pause_resume_button"
#                 ): gr.update(value="▶️ Resume", interactive=True)
#             }  # Optimistic update
#     else:
#         logger.warning(
#             "Pause/Resume clicked but agent is not running or doesn't support state."
#         )
#         return {}  # No change


async def handle_clear(webui_manager: WebuiManager):
    """Handles clicks on the 'Clear' button."""
    logger.info("Clear button clicked.")

    # Stop any running task first
    task = webui_manager.bu_current_task
    if task and not task.done():
        logger.info("Clearing requires stopping the current task.")
        webui_manager.bu_agent.stop()
        task.cancel()
        try:
            await asyncio.wait_for(task, timeout=2.0)  # Wait briefly
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        except Exception as e:
            logger.warning(f"Error stopping task on clear: {e}")
    webui_manager.bu_current_task = None

    if webui_manager.bu_controller:
        await webui_manager.bu_controller.close_mcp_client()
        webui_manager.bu_controller = None
    webui_manager.bu_agent = None

    # Reset state stored in manager
    webui_manager.bu_chat_history = []
    webui_manager.bu_response_event = None
    webui_manager.bu_user_help_response = None
    webui_manager.bu_agent_task_id = None

    logger.info("Agent state and browser resources cleared.")

    # Reset UI components
    return {
        webui_manager.get_component_by_id("browser_use_agent.chatbot"): gr.update(
            value=[]
        ),
        webui_manager.get_component_by_id("browser_use_agent.user_input"): gr.update(
            value="", placeholder="Enter your task here..."
        ),
        webui_manager.get_component_by_id("browser_use_agent.url_input"): gr.update(
            value="", placeholder="Enter the URL to analyze (optional)"
        ),
        webui_manager.get_component_by_id(
            "browser_use_agent.agent_history_file"
        ): gr.update(value=None),
        webui_manager.get_component_by_id("browser_use_agent.recording_gif"): gr.update(
            value=None
        ),
        webui_manager.get_component_by_id("browser_use_agent.browser_view"): gr.update(
            value="<div style='...'>Browser Cleared</div>"
        ),
        webui_manager.get_component_by_id("browser_use_agent.run_button"): gr.update(
            value="▶️ Submit Task", interactive=True
        ),
        webui_manager.get_component_by_id("browser_use_agent.stop_button"): gr.update(
            interactive=False),

        #Pause/resume functionality is currently disabled and not handled in the agent workflow.

        # ,
        # webui_manager.get_component_by_id(
        #     "browser_use_agent.pause_resume_button"
        # ): gr.update(value="⏸️ Pause", interactive=False),
        webui_manager.get_component_by_id("browser_use_agent.clear_button"): gr.update(
            interactive=True
        ),
    }


# --- Tab Creation Function ---


def create_browser_use_agent_tab(webui_manager: WebuiManager):
    """
    Create the run agent tab, defining UI, state, and handlers.
    """
    webui_manager.init_browser_use_agent()

    # --- Define UI Components ---
    tab_components = {}
    with gr.Column():
        chatbot = gr.Chatbot(
            lambda: webui_manager.bu_chat_history,  # Load history dynamically
            elem_id="browser_use_chatbot",
            label="Agent Interaction",
            type="messages",
            height=600,
            show_copy_button=True,
        )
        user_input = gr.Textbox(
            label="Your Task or Response",
            placeholder="Enter your task here or provide assistance when asked.",
            lines=3,
            interactive=True,
            elem_id="user_input",
        )
        url_input = gr.Textbox(
            label="Enter URL",
            placeholder="Enter the URL to analyze (optional)",
            lines=1,
            interactive=True,
            elem_id="url_input",
        )
        with gr.Row():
            stop_button = gr.Button(
                "⏹️ Stop", interactive=False, variant="stop", scale=2
            )

            #Pause/resume functionality is currently disabled and not handled in the agent workflow.

            # pause_resume_button = gr.Button(
            #     "⏸️ Pause", interactive=False, variant="secondary", scale=2, visible=True
            # )
            clear_button = gr.Button(
                "🗑️ Clear", interactive=True, variant="secondary", scale=2
            )
            run_button = gr.Button("▶️ Submit Task", variant="primary", scale=3)

        browser_view = gr.HTML(
            value="""
            <div style="width:100%; height:600px; border:1px solid #ccc; border-radius:8px; overflow:hidden;">
                <div style="background:#f8f9fa; padding:10px; border-bottom:1px solid #dee2e6;">
                    <strong>🖥️ Live Browser View</strong>
                    <span style="float:right; color:#28a745;">● Connected</span>
                </div>
                <iframe 
                    src="http://localhost:6080/vnc.html?autoconnect=true&resize=scale&password=youvncpassword&autoconnect=true&resize=scale&quality=6&compression=6" 
                    width="100%" 
                    height="calc(100% - 50px)" 
                    frameborder="0"
                    allowfullscreen
                    style="border-radius: 0 0 8px 8px;">
                </iframe>
            </div>
            """,
            label="Live Browser Automation",
            elem_id="browser_view",
            visible=True,
        )
        with gr.Column():
            gr.Markdown("### Task Outputs")
            agent_history_file = gr.File(label="Agent History JSON", interactive=False)
            recording_gif = gr.Image(
                label="Task Recording GIF",
                format="gif",
                interactive=False,
                type="filepath",
            )

    # --- Store Components in Manager ---
    tab_components.update(
        dict(
            chatbot=chatbot,
            user_input=user_input,
            url_input=url_input,
            clear_button=clear_button,
            run_button=run_button,
            stop_button=stop_button,

            #Pause/resume functionality is currently disabled and not handled in the agent workflow.

            # pause_resume_button=pause_resume_button,
            agent_history_file=agent_history_file,
            recording_gif=recording_gif,
            browser_view=browser_view,
        )
    )
    webui_manager.add_components(
        "browser_use_agent", tab_components
    )  # Use "browser_use_agent" as tab_name prefix

    all_managed_components = set(
        webui_manager.get_components()
    )  # Get all components known to manager
    run_tab_outputs = list(tab_components.values())

    async def submit_wrapper(
            components_dict: Dict[Component, Any],
    ) -> AsyncGenerator[Dict[Component, Any], None]:
        """Wrapper for handle_submit that yields its results."""
        async for update in handle_submit(webui_manager, components_dict):
            yield update

    async def stop_wrapper() -> AsyncGenerator[Dict[Component, Any], None]:
        """Wrapper for handle_stop."""
        update_dict = await handle_stop(webui_manager)
        yield update_dict

    #Pause/resume functionality is currently disabled and not handled in the agent workflow.

    # async def pause_resume_wrapper() -> AsyncGenerator[Dict[Component, Any], None]:
    #     """Wrapper for handle_pause_resume."""
    #     update_dict = await handle_pause_resume(webui_manager)
    #     yield update_dict

    async def clear_wrapper() -> AsyncGenerator[Dict[Component, Any], None]:
        """Wrapper for handle_clear."""
        update_dict = await handle_clear(webui_manager)
        yield update_dict

    # --- Connect Event Handlers using the Wrappers --
    run_button.click(
        fn=submit_wrapper, inputs=all_managed_components, outputs=run_tab_outputs
    )
    user_input.submit(
        fn=submit_wrapper, inputs=all_managed_components, outputs=run_tab_outputs
    )
    stop_button.click(fn=stop_wrapper, inputs=None, outputs=run_tab_outputs)
    
    clear_button.click(fn=clear_wrapper, inputs=None, outputs=run_tab_outputs)

    #Pause/resume functionality is currently disabled and not handled in the agent workflow.

    # pause_resume_button.click(
    #     fn=pause_resume_wrapper, inputs=None, outputs=run_tab_outputs
    # )


