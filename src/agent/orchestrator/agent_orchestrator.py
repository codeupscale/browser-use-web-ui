import logging
from langgraph.graph import StateGraph, START, END
import os
from typing import TypedDict, Any, Dict
from browser_use.agent.views import AgentHistoryList
from src.webpage.webpage_checker import WebpageChecker
from src.agent.qa_possibilty_checker.agent import QAPossibilityChecker
from src.agent.prompt_enahncer.agent import PromptEnhancerAgent
from src.agent.browser_use.browser_use_agent import BrowserUseAgent
import asyncio
from playwright.async_api import async_playwright
from openai import OpenAI



logger = logging.getLogger(__name__)

class State(TypedDict):
    user_query: str
    url: str
    browser: Any
    browser_context: Any
    controller: Any

    # Intent classification fields (now handled by QA possibility checker)
    intent_check: bool
    intent_agent_msg: str
    prompt_without_ui: str

    webpage_check: bool
    webpage_msg: str

    screenshot_taken: bool
    image_fileId: str

    extracted_snippet_agent_msg: str
    extracted_snippet: str
    snippet_check: bool

    QA_possibility_agent_msg: str
    QA_possibility_check: bool

    enhanced_prompt_agent_msg: str
    enhanced_prompt: str

    browser_result: Any

class AgentOrchestrator:
    def __init__(
        self,
        llm: Any,
        browser_config: Dict[str, Any],
        use_vision: bool = False,
        max_actions_per_step: int = 5,
        generate_gif: bool = False,
        user_query: str = "",
        url: str = "",
        register_new_step_callback: Any = None,
        done_callback_wrapper: Any = None,
        override_system_prompt: Any = None,
        extend_system_prompt: Any = None,
        planner_llm: Any = None,
        use_vision_for_planner: bool = False,
        message_callback=None
    ):
        
        self.llm = llm
        self.browser_config = browser_config
        self.use_vision = use_vision
        self.max_actions_per_step = max_actions_per_step
        self.generate_gif = generate_gif
        self.user_query = user_query
        self.url = url
        self.register_new_step_callback = register_new_step_callback
        self.done_callback_wrapper = done_callback_wrapper
        self.override_system_prompt = override_system_prompt
        self.extend_system_prompt = extend_system_prompt
        self.planner_llm = planner_llm
        self.use_vision_for_planner = use_vision_for_planner
        self.message_callback = message_callback
        self.client = OpenAI()

        self.builder = StateGraph(State)

        self.builder.add_node("webpage_checker", self.webpage_checker)
        self.builder.add_node("take_screenshot", self.take_screenshot)
        self.builder.add_node("get_image_fileId", self.get_image_fileId)
        self.builder.add_node("QA_possibility", self.QA_possibility)
        self.builder.add_node("prompt_enhancer", self.prompt_enhancer)
        self.builder.add_node("browser_ui", self.browser_ui)

        self.builder.add_edge(START, "webpage_checker")

        self.builder.add_conditional_edges(
            "webpage_checker",
            self._webpage_condition,
            {
                "take_screenshot": "take_screenshot",
                "__end__": END
            }
        )                        

        self.builder.add_conditional_edges(
            "take_screenshot",
            self._take_screenshot_condition,
            {
                "get_image_fileId": "get_image_fileId",
                "__end__": END
            }
        )
        self.builder.add_conditional_edges(
            "get_image_fileId",
            self._get_image_fileId_condition,
            {
                "QA_possibility": "QA_possibility",
                "__end__": END
            }
        )

        self.builder.add_conditional_edges(
            "QA_possibility",
            self._QA_possibility_condition,
            {
                "prompt_enhancer": "prompt_enhancer",
                "__end__": END
            }
        )

        # Add conditional edge for prompt_enhancer to handle intent classification
        self.builder.add_conditional_edges(
            "prompt_enhancer",
            self._prompt_enhancer_condition,
            {
                "browser_ui": "browser_ui",
                "__end__": END
            }
        )

        self.builder.add_edge("browser_ui", END)

        self.graph = self.builder.compile()
        self._store_graph_image(self.graph)


    async def webpage_checker(self, state: State) -> State:
        logger.info("\n\n WEBPAGE CHECKER NODE...\n")
        output =await WebpageChecker(url=self.url,message_callback=self.message_callback).exists()
        if output:
            logger.info("Webpage exists and is valid")
            state['webpage_msg'] = "Webpage exists and is valid"
            state["webpage_check"] = True
        else:
            logger.error("Webpage does not exist or is invalid")
            state['webpage_msg'] = "Webpage does not exists or is invalid"
            state["webpage_check"] = False
        return state

    def _get_output_value(self, output, key, default=None):
        if isinstance(output, dict):
            return output.get(key, default)
        return getattr(output, key, default)


    async def take_screenshot(self, state: State) -> State:

        # Paths for local development
        # save_path = "screenshot.png"
        
        # Paths for Dockerized application
        save_path = "/app/src/outputdata/screenshot.png"
        
        # Debug: Print screenshot path info
        print(f"📸 Screenshot path: {save_path}")
        print(f"📸 Screenshot directory exists: {os.path.exists(os.path.dirname(save_path))}")
        print(f"📸 Screenshot directory writable: {os.access(os.path.dirname(save_path), os.W_OK) if os.path.exists(os.path.dirname(save_path)) else 'N/A'}")
        
        try:
            logger.info("Taking screenshot...")
            print(f"🌐 Navigating to URL: {self.url}")
            if self.message_callback:
                await self.message_callback("----------------------------")
                await self.message_callback("📸 Starting screenshot agent.")
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                try:
                    await page.goto(self.url, timeout=30000, wait_until="networkidle")
                except Exception:
                    print("Networkidle timed out! Try domcontentloaded.")
                    await page.goto(self.url, timeout=30000, wait_until="domcontentloaded")
                
                if self.message_callback:
                    await self.message_callback("✅ Page loaded successfully.")
                print(f"✅ Page loaded successfully")
                
                # Wait for 2 seconds to ensure proper page rendering
                if self.message_callback:
                    await self.message_callback("⏳ Waiting for page to render properly...")
                print("⏳ Waiting for page to render properly...")
                await asyncio.sleep(2)
                
                #await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1)

                #scroll multiple times for infinite scrolling pages
                for _ in range(6):
                    await page.mouse.wheel(0, 1000)
                    await asyncio.sleep(1)

                print(f"📸 Taking screenshot and saving to: {save_path}")
                if self.message_callback:
                   await self.message_callback("📸 Taking screenshot of the page...")

                await page.screenshot(path=save_path, full_page=True)
                await browser.close()
                logger.info(f"Screenshot saved at: {save_path}")
                
                # Debug: Verify screenshot was actually saved
                if os.path.exists(save_path):
                    file_size = os.path.getsize(save_path)
                    print(f"✅ Screenshot saved successfully! Size: {file_size} bytes")
                    if self.message_callback:
                       await self.message_callback(f"✅ Screenshot saved successfully! Size: {file_size} bytes")
                    state["screenshot_taken"] = True
                else:
                    if self.message_callback:
                       await self.message_callback(f"❌ Screenshot file not found at: {save_path}")
                    state["screenshot_taken"] = False
        except Exception as e:
            logger.error(f"Error taking screenshot: {e}")
            if self.message_callback:
               await self.message_callback(f"❌ Error taking screenshot: {e}")
            state["screenshot_taken"] = False
        await self.message_callback("----------------------------")
        return state    
    
    async def get_image_fileId(self, state: State) -> State:
        logger.info("Extracting image file ID...")
        if self.message_callback:
            await self.message_callback("🖼️ Extracting image file ID...")
        try:
            # Paths for local development
            # with open("screenshot.png", "rb") as image_file:
            
            # Paths for Dockerized application
            with open("/app/src/outputdata/screenshot.png", "rb") as image_file:
                image_file_id = self.client.files.create(file=image_file, purpose="vision").id
                logger.info(f"Image file ID extracted: {image_file_id}")
                state["image_fileId"] = image_file_id
        except Exception as e:
            logger.error(f"Error extracting base64 image: {e}")
            state["image_fileId"] = ""
        return state

    async def QA_possibility(self, state: State) -> State:
        logger.info("\n\n QA POSSIBILITY CHECKER AGENT (with Intent Classification)...\n")

        try:
            user_prompt = state.get("prompt_without_ui", self.user_query)
            print(f"Running QA possibility checker with user_prompt: {user_prompt}")
            print(f"Image file ID: {state.get('image_fileId', 'NOT SET')}")
            
            output = await QAPossibilityChecker(
                llm=self.llm,
                user_prompt=user_prompt,
                image_file_id=state["image_fileId"],
                message_callback=self.message_callback
            ).run_agent()
            
            print(f"QA possibility output: {output}")
            print(f"Output type: {type(output)}")
            print(f"Output attributes: {dir(output)}")
            
            # Handle intent classification (now part of QA possibility checker)
            state["intent_check"] = output.intent
            state["intent_agent_msg"] = output.agent_msg

            print(f"Intent: {state['intent_check']}, QA Possibility: {state.get('QA_possibility_check', 'NOT SET')}")
            
            # Handle modified prompt from intent classification
            new_intent_prompt = self._get_output_value(output, "modified_prompt", "")
            if new_intent_prompt:
                logger.info(f"Modified user query: {new_intent_prompt}")
                state["prompt_without_ui"] = new_intent_prompt
            
            # Handle QA possibility
            state["QA_possibility_agent_msg"] = output.agent_msg
            state["QA_possibility_check"] = output.qa_possibility

            print(f"Intent: {state['intent_check']}, QA Possibility: {state['QA_possibility_check']}")
            print(f"State after QA possibility: {state}")
            
            logger.info(f"\n\nIntent: {state['intent_check']}, QA Possibility: {state['QA_possibility_check']}")
            return state
            
        except Exception as e:
            logger.error(f"Error in QA possibility checker: {e}")
            import traceback
            traceback.print_exc()
            # Set default values in case of error
            state["intent_check"] = False
            state["intent_agent_msg"] = f"Error in QA possibility checker: {e}"
            state["QA_possibility_agent_msg"] = f"Error in QA possibility checker: {e}"
            state["QA_possibility_check"] = False
            return state

    async def prompt_enhancer(self, state: State) -> State:
        logger.info("\n\n PROMPT ENHANCER AGENT...\n")

        user_prompt = state.get("prompt_without_ui", self.user_query)
        output = await PromptEnhancerAgent(
            llm=self.llm,
            user_prompt=user_prompt,
            image_file_id=state['image_fileId'],
            message_callback=self.message_callback
        ).run_agent()
        
        # Handle enhanced prompt
        state['enhanced_prompt_agent_msg'] = output.agent_msg
        state['enhanced_prompt'] = output.enhanced_prompt

        logger.info(f"\n\nEnhanced prompt: {state['enhanced_prompt']}")
        return state

    async def browser_ui(self, state: State) -> State:
        if self.message_callback:
            await self.message_callback("🧪 Browser UI Agent Started...")

        logger.info("\n\n BROWSER UI AGENT...\n")
        try:
            # Initialize BrowserUseAgent with all required parameters
            task = f"{state['enhanced_prompt']} \n\n THE URL: {self.url}"
            logger.info(f"task to browser use agent: {task}")
            browser_agent = BrowserUseAgent(
                task=task,
                llm=self.llm,
                browser=state["browser"],
                browser_context=state["browser_context"],
                controller=state["controller"],
                use_vision=self.use_vision,
                max_actions_per_step=self.max_actions_per_step,
                generate_gif=self.generate_gif,
                register_new_step_callback=self.register_new_step_callback,
                register_done_callback=self.done_callback_wrapper,      # We'll handle this in the run method
                override_system_message=self.override_system_prompt,     # Add if needed
                extend_system_message=self.override_system_prompt,       # Add if needed
                max_input_tokens=128000,          # Default value
                tool_calling_method="auto",       # Default value
                planner_llm=self.planner_llm,                 # Add if needed
                use_vision_for_planner=self.use_vision_for_planner,     # Default value
                source="webui"
            )
            
            # Run the browser agent
            result = await browser_agent.run(max_steps=100)
            if self.message_callback:
               await self.message_callback("✅ Browser UI Agent Finished...")

            # Store the result in state
            state["browser_result"] = result
            return state
            
        except Exception as e:
            logger.error(f"Error in browser UI agent: {e}")
            state["browser_result"] = None
            return state

    def _intent_condition(self, state: State) -> Any:
        return "webpage_checker" if state.get("intent_check") else END

    def _webpage_condition(self, state: State) -> Any:
        return "take_screenshot" if state.get("webpage_check") else END

    def _take_screenshot_condition(self, state: State) -> Any:
        return "get_image_fileId" if state.get("screenshot_taken") else END
    
    def _get_image_fileId_condition(self, state: State) -> Any:
        return "QA_possibility" if state.get("image_fileId") else END

    def _QA_possibility_condition(self, state: State) -> Any:
        # Check if intent is true and QA is possible
        # If intent is false, stop the flow with error message
        intent_check = state.get("intent_check", False)
        qa_possibility_check = state.get("QA_possibility_check", False)
        
        print(f"QA possibility condition check - Intent: {intent_check}, QA Possibility: {qa_possibility_check}")
        
        if not intent_check:
            # Intent is not related to QA, stop the flow
            print("Stopping flow: Intent is not QA-related")
            return END
        elif intent_check and qa_possibility_check:
            # Intent is true and QA is possible, continue to prompt enhancer
            print("Continuing to prompt enhancer: Intent and QA possibility both true")
            return "prompt_enhancer"
        else:
            # Intent is true but QA is not possible, stop the flow
            print("Stopping flow: Intent is QA-related but QA is not possible")
            return END

    def _prompt_enhancer_condition(self, state: State) -> Any:
        # Check if enhanced prompt exists
        return "browser_ui" if state.get("enhanced_prompt") else END

    async def run(self, task: str, browser: Any = None, browser_context: Any = None, controller: Any = None) -> AgentHistoryList:
        try:
            initial_state = {
                "user_query": task,
                "url": self.url,
                "browser": browser,
                "browser_context": browser_context,
                "controller": controller
            }
            
            final_state = await self.graph.ainvoke(initial_state)
            
            # Check if intent classification or QA possibility failed
            intent_check = final_state.get("intent_check", False)
            intent_msg = final_state.get("intent_agent_msg", "")
            qa_possibility_check = final_state.get("QA_possibility_check", False)
            
            if not intent_check:
                # Intent is not related to QA, return error message
                current_state = {
                    "intent_classification": {
                        "intent": False,
                        "message": intent_msg or "Intent is not related to QA testing"
                    },
                    "webpage_check": {
                        "check": final_state.get("webpage_check", False),
                        "message": final_state.get("webpage_msg", "")
                    },
                    "snippet_extraction": {
                        "check": False,
                        "message": "",
                        "snippet": ""
                    },
                    "qa_possibility": {
                        "check": False,
                        "message": "No QA possibility check needed - intent not QA-related"
                    },
                    "enhanced_prompt": {
                        "prompt": "",
                        "message": "No prompt enhancement needed - intent not QA-related"
                    },
                    "evaluation_previous_goal": "Intent classification failed",
                    "memory": "Task stopped due to non-QA intent",
                    "next_goal": "Task stopped"
                }
                
                return AgentHistoryList(
                    history=[
                        {
                            "model_output": {
                                "current_state": current_state,
                                "action": []
                            },
                            "result": [{
                                "is_done": True,
                                "success": False,
                                "extracted_content": f"Error: {intent_msg or 'Intent is not related to QA testing. Please provide a QA-related query.'}"
                            }],
                            "state": {
                                "title": "",
                                "tabs": [],
                                "interacted_element": [],
                                "url": self.url
                            }
                        }
                    ]
                )
            elif intent_check and not qa_possibility_check:
                # Intent is QA-related but QA is not possible on the snippet
                current_state = {
                    "intent_classification": {
                        "intent": True,
                        "message": intent_msg
                    },
                    "webpage_check": {
                        "check": final_state.get("webpage_check", False),
                        "message": final_state.get("webpage_msg", "")
                    },
                    "snippet_extraction": {
                        "check": False,
                        "message": "",
                        "snippet": ""
                    },
                    "qa_possibility": {
                        "check": False,
                        "message": final_state.get("QA_possibility_agent_msg", "")
                    },
                    "enhanced_prompt": {
                        "prompt": "",
                        "message": "No prompt enhancement needed - QA not possible on snippet"
                    },
                    "evaluation_previous_goal": "QA possibility check failed",
                    "memory": "Task stopped due to QA not being possible on the snippet",
                    "next_goal": "Task stopped"
                }
                
                return AgentHistoryList(
                    history=[
                        {
                            "model_output": {
                                "current_state": current_state,
                                "action": []
                            },
                            "result": [{
                                "is_done": True,
                                "success": False,
                                "extracted_content": f"Error: {final_state.get('QA_possibility_agent_msg', 'QA is not possible on the extracted snippet.')}"
                            }],
                            "state": {
                                "title": "",
                                "tabs": [],
                                "interacted_element": [],
                                "url": self.url
                            }
                        }
                    ]
                )
            
            # Create a base state dictionary with default values for successful execution
            current_state = {
                "intent_classification": {
                    "intent": intent_check,
                    "message": intent_msg
                },
                "webpage_check": {
                    "check": final_state.get("webpage_check", False),
                    "message": final_state.get("webpage_msg", "")
                },
                "snippet_extraction": {
                    "check": False,
                    "message": "",
                    "snippet": ""
                },
                "qa_possibility": {
                    "check": final_state.get("QA_possibility_check", False),
                    "message": final_state.get("QA_possibility_agent_msg", "")
                },
                "enhanced_prompt": {
                    "prompt": final_state.get("enhanced_prompt", ""),
                    "message": final_state.get("enhanced_prompt_agent_msg", "")
                },
                "evaluation_previous_goal": "Previous goal completed successfully",
                "memory": "Task completed successfully",
                "next_goal": "Task completed"
            }
               
            return AgentHistoryList(
                history=[
                    {
                        "model_output": {
                            "current_state": current_state,
                            "action": []  # Empty list for actions
                        },
                        "result": [{
                            "is_done": True,
                            "success": True,
                            "extracted_content": str(final_state.get("browser_result", "Task completed successfully"))
                        }],
                        "state": {
                            "title": "",
                            "tabs": [],
                            "interacted_element": [],
                            "url": self.url
                        }
                    }
                ]
            )
        except Exception as e:
            logger.error(f"Error in agent orchestration: {e}")
            raise

    def _store_graph_image(self, graph, output_path=None):
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            output_path = output_path or os.path.join(base_dir, "qa_graph.png")
            png_bytes = graph.get_graph().draw_mermaid_png()
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(png_bytes)
            
            print("\n\n\n\n\n\n" , graph.get_graph().draw_mermaid(), "\n\n\n\n")

            logger.info(f"Graph image saved to {output_path}")
        except Exception as e:
            logger.error(f"Failed to save LangGraph image: {e}")
