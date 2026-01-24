import gradio as gr
import llm 
from crisprgpt.logic import GradioMachineStateClass, concurrent_gradio_state_machine
from crisprgpt import entry
from util import get_logger
import uuid 
import os
from pathlib import Path

logger = get_logger(__name__)
Path("log").mkdir(exist_ok=True)

# Global state
current_state = None
current_session_id = None

def initialize_session():
    """Initialize a new session"""
    global current_state, current_session_id
    
    full_task_list = [entry.EntryState]
    current_state = GradioMachineStateClass(full_task_list=full_task_list)
    current_session_id = str(uuid.uuid4().hex)
    concurrent_gradio_state_machine.reset(current_state)
    
    try:
        init_messages = concurrent_gradio_state_machine.loop(None, current_state)
        return [(None, msg) for msg in init_messages]
    except Exception as e:
        logger.error(f"Initialization error: {e}")
        return [(None, "CRISPR-GPT ready! How can I assist you with molecular biology?")]

def save_chat(history, session_id):
    """Save chat history to file"""
    try:
        to_save = ""
        for user_msg, bot_msg in history:
            if user_msg:
                to_save += f"### User: \n{user_msg}\n\n"
            if bot_msg:
                to_save += f"### CRISPR-GPT: \n{bot_msg}\n\n"
        
        file_path = f"log/{session_id}.txt"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(to_save)
        return file_path
    except Exception as e:
        logger.error(f"Save error: {e}")
        return ""

def chat_respond(message, history):
    """Process user message"""
    global current_state, current_session_id
    
    try:
        if not message.strip():
            return history, ""
        
        # Get bot response
        bot_messages = concurrent_gradio_state_machine.loop(message, current_state)
        
        # Add to history
        for bot_msg in bot_messages:
            history.append((message, str(bot_msg)))
            message = None  # Only show user message once
        
        # Save chat
        save_chat(history, current_session_id)
        
        return history, ""
        
    except Exception as e:
        logger.error(f"Chat error: {e}")
        history.append((message, f"Error: {str(e)}"))
        return history, ""

def reset_chat():
    """Reset the chat"""
    return initialize_session(), ""

# Custom CSS for better chat styling  
custom_css = """
/* Override all fonts in the entire app */
* {
    font-family: Arial, sans-serif !important;
}

/* Specific targeting for chatbot */
[data-testid="chatbot"] * {
    font-family: Arial, sans-serif !important;
    font-size: 14px !important;
}

/* Code elements */
pre, code {
    font-family: Courier, monospace !important;
}
"""

# Create the interface
with gr.Blocks(title="CRISPR-GPT", theme=gr.themes.Soft(), css=custom_css) as demo:
    
    gr.Markdown("# 🧬 CRISPR-GPT")
    gr.Markdown("*AI Assistant for gene editing*")
    
    chatbot = gr.Chatbot(
        height=600,
        type="tuples"  # Use tuples for better compatibility
    )
    
    with gr.Row():
        msg = gr.Textbox(
            placeholder="Ask about gene-editing...",
            container=False,
            scale=4
        )
        send_btn = gr.Button("Send", variant="primary")
    
    with gr.Row():
        reset_btn = gr.Button("🔄 Reset Session")
    
    # Event handlers
    send_btn.click(chat_respond, [msg, chatbot], [chatbot, msg])
    msg.submit(chat_respond, [msg, chatbot], [chatbot, msg])
    
    reset_btn.click(reset_chat, outputs=[chatbot, msg])
    
    # Initialize on load
    demo.load(initialize_session, outputs=chatbot)

if __name__ == "__main__":
    demo.queue()
    demo.launch(
        share=True,
        allowed_paths=["log/"],
        show_api=False,
        inbrowser=False
    ) 