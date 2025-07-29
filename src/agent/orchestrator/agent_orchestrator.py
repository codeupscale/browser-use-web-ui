import logging
from langgraph.graph import StateGraph, START, END
import os
from typing import TypedDict, Any, Dict
from browser_use.agent.views import AgentHistoryList

from src.agent.intent_classifier.agent import IntentClassifierAgent
from src.webpage.webpage_checker import WebpageChecker
from src.agent.snippet_extractor.agent import SnippetExtractorAgent
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
        self.client = OpenAI()

        self.builder = StateGraph(State)

        self.builder.add_node("intent_classifier", self.intent_classifier)
        self.builder.add_node("webpage_checker", self.webpage_checker)
        # self.builder.add_node("snippet_extractor", self.snippet_extractor)
        self.builder.add_node("take_screenshot", self.take_screenshot)
        self.builder.add_node("get_image_fileId", self.get_image_fileId)
        self.builder.add_node("QA_possibility", self.QA_possibility)
        self.builder.add_node("prompt_enhancer", self.prompt_enhancer)
        self.builder.add_node("browser_ui", self.browser_ui)


        self.builder.add_edge(START, "intent_classifier")

        self.builder.add_conditional_edges(
            "intent_classifier",
            self._intent_condition,
            {
                "webpage_checker": "webpage_checker",
                "__end__": END
            }
        )

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

        self.builder.add_edge("prompt_enhancer", "browser_ui")
        self.builder.add_edge("browser_ui", END)

        self.graph = self.builder.compile()
        self._store_graph_image(self.graph)

    def intent_classifier(self, state: State) -> State:
        logger.info("\n\n INTENT CLASSIFIER NODE...\n")
        output = IntentClassifierAgent(llm=self.llm, user_prompt=self.user_query).run_agent()
        state["intent_check"] = output.intent
        state["intent_agent_msg"] = output.agent_msg

        new_intent_prompt = self._get_output_value(output, "modified_prompt", "")
        if new_intent_prompt:
            logger.info(f"Modified user query: {new_intent_prompt}")
            state["prompt_without_ui"] = new_intent_prompt
        else:
            logger.info("No modifications made to the user query.")
        
        return state

    def webpage_checker(self, state: State) -> State:
        logger.info("\n\n WEBPAGE CHECKER NODE...\n")
        output = WebpageChecker(url=self.url).exists()
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

        save_path = "screenshot.png"
        try:
            logger.info("Taking screenshot...")
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(self.url, timeout=60000, wait_until="networkidle")
                
                #await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1)

                #scroll multiple times for infinite scrolling pages
                for _ in range(6):
                    await page.mouse.wheel(0, 1000)
                    await asyncio.sleep(1)

                await page.screenshot(path=save_path, full_page=True)
                await browser.close()
                logger.info(f"Screenshot saved at: {save_path}")
                
                state["screenshot_taken"] = True
        except Exception as e:
            logger.error(f"Error taking screenshot: {e}")
            state["screenshot_taken"] = False

        return state    
    
    def get_image_fileId(self, state: State) -> State:
        logger.info("Extracting image file ID...")
        try:
            with open("screenshot.png", "rb") as image_file:
                image_file_id = self.client.files.create(file=image_file, purpose="vision").id
                logger.info(f"Image file ID extracted: {image_file_id}")
                state["image_fileId"] = image_file_id
        except Exception as e:
            logger.error(f"Error extracting base64 image: {e}")
            state["image_fileId"] = ""
        return state

    def QA_possibility(self, state: State) -> State:
        logger.info("\n\n QA POSSIBILTY CHECKER AGENT...\n")

        user_prompt = state.get("prompt_without_ui", self.user_query)
        output = QAPossibilityChecker(
            llm=self.llm,
            user_prompt=user_prompt,
            image_file_id=state["image_fileId"],
        ).run_agent()
        state["QA_possibility_agent_msg"] = output.agent_msg
        state["QA_possibility_check"] = output.qa_possibility
        return state

    def prompt_enhancer(self, state: State) -> State:
        logger.info("\n\n PROMPT ENHANCER AGENT...\n")

        user_prompt = state.get("prompt_without_ui", self.user_query)
        output = PromptEnhancerAgent(
            llm=self.llm,
            user_prompt=user_prompt,
            image_file_id=state['image_fileId']
        ).run_agent()
        state['enhanced_prompt_agent_msg'] = output.agent_msg
        state['enhanced_prompt'] = output.enhanced_prompt

        logger.info(f"\n\nEnhanced prompt: {state['enhanced_prompt']}")
        return state

    async def browser_ui(self, state: State) -> State:
        logger.info("\n\n BROWSER UI AGENT...\n")
        try:
            # Initialize BrowserUseAgent with all required parameters
            task = f"{state['enhanced_prompt']} URL: {self.url}"
            logger.info("task to browser use agent: " ,task )
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
            result = await browser_agent.run(max_steps=25)
            
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
        return "prompt_enhancer" if state.get("QA_possibility_check") else END

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
            
            # Create a base state dictionary with default values
            current_state = {
                "intent_classification": {
                    "intent": final_state.get("intent_check", False),
                    "message": final_state.get("intent_agent_msg", "")
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
                        # "result": [{
                        #     "type": "success",
                        #     "message": final_state.get("browser_result", "Task completed successfully")
                        # }],
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
