from typing import AsyncGenerator, Awaitable, Callable, Dict, Any
import asyncio
import json
import logging
import os
import uuid
from typing import Any, AsyncGenerator, Dict, Optional
import os, time
from src.browser.browser_recorder import BrowserRecorder
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
    recorder = BrowserRecorder()
    browser_context = await recorder.setup_recording(playwright_browser)

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
        page = await browser_context.new_page()
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
        await page.close()
    except Exception as e:
        print(f"⚠️ Could not maximize browser window: {e}")

    # 3. Initialize controller
    controller = CustomController()

    if message_callback:
        await message_callback("🧠 Initializing LLM...")

    llm = await _initialize_llm(
        provider="openai",
        model_name="gpt-4o",
        temperature=0.6,
        api_key=os.getenv("OPENAI_API_KEY")
    )
    
    # 4. Step handler with WebSocket message sending
    async def handle_step(state: BrowserState, output: AgentOutput, step_num: int):
        step_dir = os.path.join(output_dir, f"step_{step_num}")
        os.makedirs(step_dir, exist_ok=True)


        evaluation = getattr(output.current_state, "evaluation_previous_goal", "")
        memory = getattr(output.current_state, "memory", "")
        next_goal = getattr(output.current_state, "next_goal", "")
        actions = output.actions_taken if hasattr(output, "actions_taken") else []

        # Send to frontend via WebSocket
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

    print("\n\n\n\n\n history:", history)

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

    try:
        await recorder.save_recording()
    except Exception as e:
        logger.warning(f"Could not save recording: {e}")

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
        api_key: Optional[str] = None
) -> BaseChatModel:
    """Initialize LLM instance"""
    logger.info(f"Initializing LLM: {provider}/{model_name}")
    return llm_provider.get_llm_model(
        provider=provider,
        model_name=model_name,
        temperature=temperature,
        api_key=api_key,
    )



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
            

            webui_manager.get_component_by_id(
                "browser_use_agent.clear_button"
            ): gr.update(interactive=True),
        }
    


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