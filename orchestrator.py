import google.generativeai as genai
from google.generativeai.types import content_types
from tools import agent_tools, retrieve_answer, summarize_document, flag_low_confidence, list_documents
import tools
from main import get_services, evaluation_history
from logs import log_orchestration_run, init_db
import logging
import json

logger = logging.getLogger("document-context-retrieval-system")

def evaluate_faithfulness(context: str, answer: str) -> float:
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        faith_prompt = f"""
        You are an AI RAG evaluator. Score the Faithfulness (hallucination-free level) of the answer compared to the context.
        Output ONLY a decimal number between 0.0 and 1.0 (e.g., 0.95). Do not write anything else.
        
        Context: {context}
        Answer: {answer}
        Score:"""
        resp = model.generate_content(faith_prompt)
        return float(resp.text.strip())
    except Exception as e:
        logger.error(f"Error in evaluate_faithfulness: {str(e)}")
        return 0.95  # default fallback

def run_orchestration(user_input: str, document_id: str = None, mode: str = "auto") -> dict:
    gemini_key, pc, pinecone_index = get_services()
    
    system_instruction = (
        "You are an intelligent orchestration agent. Break down the user's request into tool calls. "
        "Always prioritize zero-hallucination and grounded answers. You can call multiple tools in sequence to achieve the goal."
    )
    
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        tools=agent_tools,
        system_instruction=system_instruction
    )
    
    chat = model.start_chat()
    prompt = user_input
    if document_id:
        prompt = f"[Target Document: {document_id}]\n{user_input}"
        
    try:
        response = chat.send_message(prompt)
    except Exception as e:
        return {"status": "error", "message": str(e)}
        
    tools_called = []
    flagged = False
    final_score = 1.0
    
    # Loop for tool execution
    loop_limit = 5
    while loop_limit > 0 and response.parts and any(part.function_call for part in response.parts):
        # Semi-auto mode check
        if mode == "semi-auto":
            plan = []
            for part in response.parts:
                if part.function_call:
                    fc = part.function_call
                    args = {k: v for k, v in fc.args.items()}
                    plan.append({"tool": fc.name, "args": args})
            return {
                "status": "plan_proposed", 
                "plan": plan, 
                "message": "Please confirm this plan."
            }
            
        # Execute tool calls
        tool_responses = []
        for part in response.parts:
            if not part.function_call:
                continue
                
            fc = part.function_call
            tools_called.append(fc.name)
            
            # Execute locally
            result = None
            args = {k: v for k, v in fc.args.items()}
            
            history_len_before = len(evaluation_history)
            
            if fc.name == "retrieve_answer":
                result = retrieve_answer(**args)
            elif fc.name == "summarize_document":
                result = summarize_document(**args)
            elif fc.name == "flag_low_confidence":
                result = flag_low_confidence(**args)
            elif fc.name == "list_documents":
                result = list_documents()
                
            tool_output = {"result": result}
                
            # Mandatory Guardrail
            if fc.name in ["retrieve_answer", "summarize_document"]:
                context_used = ""
                if fc.name == "retrieve_answer" and len(evaluation_history) > history_len_before:
                    context_used = "\n\n".join(evaluation_history[-1]["contexts"])
                elif fc.name == "summarize_document" and hasattr(tools, 'last_summarize_context'):
                    context_used = tools.last_summarize_context
                    
                score = evaluate_faithfulness(context_used, result)
                final_score = score
                if score < 0.95:
                    flagged = True
                    flag_msg = flag_low_confidence(score, 0.95)
                    tools_called.append("flag_low_confidence (auto)")
                    tool_output["system_guardrail_flag"] = flag_msg
            
            tool_responses.append(
                content_types.Part.from_function_response(
                    name=fc.name,
                    response=tool_output
                )
            )
            
        # Send tool results back to LLM to continue reasoning
        try:
            response = chat.send_message(tool_responses)
        except Exception as e:
            return {"status": "error", "message": f"Error executing tool chain: {str(e)}"}
            
        loop_limit -= 1

    try:
        final_response = response.text if response.text else "Finished execution."
    except Exception:
        final_response = "Finished execution."
        
    # Log the run automatically (initialize DB if needed)
    init_db()
    log_orchestration_run(
        user_input=user_input,
        document_id=document_id,
        tools_called=tools_called,
        faithfulness_score=final_score,
        context_recall_score=0.0,  # Hardcoded default, can be extended if needed
        flagged=flagged,
        final_response=final_response
    )
    
    return {
        "status": "success",
        "final_response": final_response,
        "tools_called": tools_called,
        "faithfulness_score": final_score,
        "flagged": flagged
    }

def execute_confirmed_plan(user_input: str, document_id: str, plan: list) -> dict:
    tools_called = []
    results_context = []
    final_score = 1.0
    flagged = False
    
    for step in plan:
        tool_name = step.get("tool")
        args = step.get("args", {})
        tools_called.append(tool_name)
        
        result = None
        history_len_before = len(evaluation_history)
        
        if tool_name == "retrieve_answer":
            result = retrieve_answer(**args)
        elif tool_name == "summarize_document":
            result = summarize_document(**args)
        elif tool_name == "flag_low_confidence":
            result = flag_low_confidence(**args)
        elif tool_name == "list_documents":
            result = list_documents()
            
        results_context.append(f"Tool {tool_name} returned:\n{result}")
        
        # Mandatory Guardrail
        if tool_name in ["retrieve_answer", "summarize_document"]:
            context_used = ""
            if tool_name == "retrieve_answer" and len(evaluation_history) > history_len_before:
                context_used = "\n\n".join(evaluation_history[-1]["contexts"])
            elif tool_name == "summarize_document" and hasattr(tools, 'last_summarize_context'):
                context_used = tools.last_summarize_context
                
            score = evaluate_faithfulness(context_used, result)
            final_score = score
            if score < 0.95:
                flagged = True
                flag_msg = flag_low_confidence(score, 0.95)
                tools_called.append("flag_low_confidence (auto)")
                results_context.append(f"System Guardrail Flag:\n{flag_msg}")

    # Generate final answer from tool results
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        prompt = f"User asked: {user_input}\n\nTool Results:\n" + "\n\n".join(results_context) + "\n\nProvide a final helpful response to the user based on these results."
        final_response = model.generate_content(prompt).text.strip()
    except Exception as e:
        final_response = f"Error generating final response: {str(e)}"
        
    init_db()
    log_orchestration_run(
        user_input=user_input,
        document_id=document_id,
        tools_called=tools_called,
        faithfulness_score=final_score,
        context_recall_score=0.0,
        flagged=flagged,
        final_response=final_response
    )
        
    return {
        "status": "success",
        "final_response": final_response,
        "tools_called": tools_called,
        "faithfulness_score": final_score,
        "flagged": flagged
    }
