from .logic import BaseState, Result_ProcessUserInput, BaseUserInputState, StateFinal
from llm import OpenAIChat
from . import base_editing, knockout, prime_editing, act_rep, plasmid_insert_design
from .automation import StateAutomate

PROMPT_REQUEST_ENTRY = """Welcome to CRISPR-GPT. I can help with the following tasks. Please select 
one to continue.

1. Meta-Mode (Step-by-Step Guidance on Pre-defined Meta-Task)
2. Auto-Mode (Customized Guidance on Free-style User Request)
"""

PROMPT_PROCESS_ENTRY = """
Please act as an expert in CRISPR technology. Given the user instruction and user input, think step by step and generate a choice for the user. Please format your response and make sure it is parsable by JSON.

User Instructions:

"Welcome to CRISPR-GPT. I can help with the following tasks. Please select 
one to continue.

1. Meta-Mode (Step-by-Step Guidance on Pre-defined Meta-Task)
2. Auto-Mode (Customized Guidance on Free-style User Request)
"

User Input:

"{user_message}"

Response format:

{{
"Thoughts": "<thoughts>",
"Choice": "<choice>"  ## output number only
}}"""


class EntryState(BaseState):
    request_user_input = False

    @classmethod
    def step(cls, user_message, **kwargs):
        return Result_ProcessUserInput(response=PROMPT_REQUEST_ENTRY), EntryStateChoice


class EntryStateChoice(BaseUserInputState):
    prompt_process = PROMPT_PROCESS_ENTRY

    @classmethod
    def NextState(cls, choice):
        if choice.lower() in ["1", "i", "(1)", "(i)"]:
            return MetaStateEntry
        elif choice.lower() in ["2", "ii", "(2)", "(ii)"]:
            return StateAutomate
        else:
            return cls

    @classmethod
    def step(cls, user_message, **kwargs):
        prompt = cls.prompt_process.format(user_message=user_message)
        response = OpenAIChat.chat(prompt)
        
        # Format response properly instead of showing raw dictionary
        choice = response.get("Choice", "")
        thoughts = response.get("Thoughts", "")
        
        formatted_response = f"**Selection Made**\n\n**Choice:** {choice}\n\n**Reasoning:** {thoughts}"
        
        return Result_ProcessUserInput(
            status="success",
            thoughts=thoughts,
            result=choice,
            response=formatted_response,
        ), cls.NextState(choice)


PROMPT_REQUEST_META = """Please select the general gene editing scenarios to continue.
1. Generating a Knockout Using CRISPR.
2. CRISPR Base Editing Without Double-Strand Breaks. (Not Supported in Lite version)
3. Generating Small Insertion/deletion/base editing through Prime Editing. (Not Supported in Lite version)
4. Activation or Repression of Target Genes Using CRISPR. (Not Supported in Lite version)
5. Designing an Expression Plasmid.
"""

PROMPT_PROCESS_META = """
Please act as an expert in CRISPR technology and molecular biology. Given the user instruction and user input, think step by step and generate a choice for the user. Please format your response and make sure it is parsable by JSON.

User Instructions:

"Please select the general gene editing scenarios to continue.
1. Generating a Knockout Using CRISPR.
2. CRISPR Base Editing Without Double-Strand Breaks.
3. Generating Small Insertion/deletion/base editing through Prime Editing.
4. Activation or Repression of Target Genes Using CRISPR.
5. Designing an Expression Plasmid.
"

User Input:

"{user_message}"

Response format:

{{
"Thoughts": "<thoughts>",
"Choice": "<choice>"  ## output number only
}}"""


class MetaStateEntry(BaseState):
    request_user_input = False

    @classmethod
    def step(cls, user_message, **kwargs):
        return Result_ProcessUserInput(response=PROMPT_REQUEST_META), MetaStateChoice


class MetaStateChoice(BaseUserInputState):
    prompt_process = PROMPT_PROCESS_META

    @classmethod
    def NextState(cls, choice):
        if choice.lower() in ["1", "i", "(1)", "(i)"]:
            return [
                knockout.StateEntry,
                knockout.StateStep1, 
                knockout.StateStep3, 
                StateFinal,
            ]
        elif choice.lower() in ["2", "ii", "(2)", "(ii)"]:
            return [
                base_editing.StateError,
                StateFinal,
            ]
        elif choice.lower() in ["3", "iii", "(3)", "(iii)"]:
            return [
                prime_editing.StateError,
                StateFinal,
            ]
        elif choice.lower() in ["4", "iv", "(4)", "(iv)"]:
            return [
                act_rep.StateError,
                StateFinal,
            ]
        elif choice.lower() in ["5", "v", "(5)", "(v)"]:
            return [
                plasmid_insert_design.StateEntry,
                StateFinal,
            ]
        else:
            return cls

    @classmethod
    def step(cls, user_message, **kwargs):
        prompt = cls.prompt_process.format(user_message=user_message)
        response = OpenAIChat.chat(prompt)
        
        # Format response properly instead of showing raw dictionary
        choice = response.get("Choice", "")
        thoughts = response.get("Thoughts", "")
        
        formatted_response = f"**Selection Made**\n\n**Choice:** {choice}\n\n**Reasoning:** {thoughts}"
        
        return Result_ProcessUserInput(
            status="success",
            thoughts=thoughts,
            result=choice,
            response=formatted_response,
        ), cls.NextState(choice)
