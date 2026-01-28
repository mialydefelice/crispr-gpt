import pandas as pd
import re
from .plasmid_insert_design_constant import *
from .expression_plasmid_constant import *
from .logic import BaseState, Result_ProcessUserInput, BaseUserInputState
from .gene_identifier import GeneIdentifier
from .apis.parse_plasmid_library import PlasmidLibraryReader
from .plasmid_mcs_handler import MCSHandler
from .biomni_integration import get_biomni_agent
from llm import OpenAIChat
import time
import json
from util import get_logger

logger = get_logger(__name__)


def format_json_response(data, title=None):
    """Format a dictionary/JSON response as a Markdown code block for better Gradio rendering.
    
    Args:
        data: Dictionary to format
        title: Optional title to display before the code block
        
    Returns:
        Formatted string with title and code block
    """
    json_str = json.dumps(data, indent=2)
    formatted = ""
    if title:
        formatted += f"**{title}**\n\n"
    formatted += f"```json\n{json_str}\n```\n\n"
    return formatted


class StateEntry(BaseState):
    """Entry point state for the expression plasmid design workflow.
    
    Displays initial greeting and routes to plan approval. This state
    does not request user input, only provides the entry prompt.
    """
    request_user_input = False

    @classmethod
    def step(cls, user_message, **kwargs):
        """Display entry message and transition to plan approval.
        
        Args:
            user_message: Not used at entry point
            **kwargs: Additional context (not used)
            
        Returns:
            Tuple of (Result_ProcessUserInput, next_state)
        """
        return Result_ProcessUserInput(response=""), PlanApproval


class PlanApproval(BaseUserInputState):
    """State for user to approve the overall workflow plan.
    
    Shows the three-step process and asks user to confirm before proceeding.
    """
    prompt_process = PROMPT_PROCESS_PLAN_APPROVAL
    request_message = PROMPT_REQUEST_PLAN_APPROVAL

    @classmethod
    def step(cls, user_message, **kwargs):
        """Process user's approval of the workflow plan.
        
        Args:
            user_message: User's yes/no response
            **kwargs: Additional context from workflow
            
        Returns:
            Tuple of (Result_ProcessUserInput, next_state)
                - Routes to BackboneSelectionChoice if approved
                - Routes back to PlanApproval if user has concerns
        """
        prompt = cls.prompt_process.format(user_message=user_message)
        response = OpenAIChat.chat(prompt, use_GPT4=True)
        
        action = response.get("Action", "").lower()
        
        if "proceed" in action:
            next_state = BackboneSelectionChoice
        else:
            next_state = StateEntry  # IF they dont like the plan, go back
        
        return (
            Result_ProcessUserInput(
                status="success",
                result=response,
                response="",
            ),
            next_state,
        )


class BackboneSelectionChoice(BaseUserInputState):
    """State for choosing backbone selection method.
    
    Presents 4 methods for providing plasmid backbone:
    1. Choose from library (pcDNA3.1(+) or pAG)
    2. Provide name AND sequence
    3. Provide just the name
    4. Describe what you need
    """
    prompt_process = PROMPT_PROCESS_BACKBONE_SELECTION
    request_message = PROMPT_REQUEST_BACKBONE_SELECTION

    @classmethod
    def step(cls, user_message, **kwargs):
        """Process user's choice for backbone selection method.
        
        Routes to appropriate state based on selection.
        
        Args:
            user_message: User's choice (1, 2, 3, or 4)
            **kwargs: Additional context from workflow
            
        Returns:
            Tuple of (Result_ProcessUserInput, next_state)
                - Routes to BackboneLibrarySelection if choice 1
                - Routes to CustomBackboneNameAndSequence if choice 2
                - Routes to CustomBackboneNameOnly if choice 3
                - Routes to CustomBackboneDescription if choice 4
        """
        prompt = cls.prompt_process.format(user_message=user_message)
        response = OpenAIChat.chat(prompt, use_GPT4=True)
        
        choice = response.get("Choice", "").strip()
        
        if choice == "1":
            next_state = BackboneLibrarySelection
        elif choice == "2":
            next_state = CustomBackboneNameAndSequence
        elif choice == "3":
            next_state = CustomBackboneNameOnly
        elif choice == "4":
            next_state = CustomBackboneDescription
        else:
            # Default to library if unclear
            next_state = BackboneLibrarySelection
        
        return (
            Result_ProcessUserInput(
                status="success",
                result=response,
                response="",
            ),
            next_state,
        )


class BackboneLibrarySelection(BaseUserInputState):
    """State for selecting from standard library (pcDNA3.1(+) or pAG).
    
    Displays detailed information about each backbone option.
    """
    prompt_process = PROMPT_PROCESS_LIBRARY_SELECTION
    request_message = PROMPT_REQUEST_LIBRARY_SELECTION

    @classmethod
    def step(cls, user_message, **kwargs):
        """Process user's selection from library.
        
        Args:
            user_message: User's choice (1 for pcDNA3.1+ or 2 for pAG)
            **kwargs: Additional context from workflow
            
        Returns:
            Tuple of (Result_ProcessUserInput, next_state)
                - Routes to GeneInsertChoice with selected backbone stored
        """
        prompt = cls.prompt_process.format(user_message=user_message)
        response = OpenAIChat.chat(prompt, use_GPT4=True)
        
        selection = response.get("Selection", "").lower()
        
        # Store the selected backbone in the response result
        backbone_name = "pcDNA3.1(+)" if "pcdna" in selection else "pAG" if "pag" in selection else "Unknown"
        
        return (
            Result_ProcessUserInput(
                status="success",
                result={
                    "BackboneName": backbone_name,
                    "SelectionMethod": "library",
                    "Reasoning": response.get("Reasoning", ""),
                },
                response="",
            ),
            GeneInsertChoice,
        )


class CustomBackboneNameAndSequence(BaseUserInputState):
    """State for collecting custom plasmid backbone name AND sequence.
    
    User provides both plasmid name and the complete sequence.
    """
    prompt_process = PROMPT_PROCESS_CUSTOM_BACKBONE_EXPRESSION
    request_message = PROMPT_REQUEST_BACKBONE_NAMESEQ

    @classmethod
    def step(cls, user_message, **kwargs):
        """Process custom backbone name and sequence input.
        
        Args:
            user_message: User input with plasmid name and sequence
            **kwargs: Additional context from workflow
            
        Returns:
            Tuple of (Result_ProcessUserInput, next_state)
                - Routes to GeneInsertChoice on success
                - Routes back on error if sequence not found
        """
        prompt = cls.prompt_process.format(user_message=user_message)
        response = OpenAIChat.chat(prompt, use_GPT4=True)

        sequence_provided = response.get("SequenceProvided", False)
        sequence_extracted = response.get("SequenceExtracted", "")
        backbone_name = response.get("BackboneName", "").strip()
        
        if not sequence_provided or not sequence_extracted or len(sequence_extracted) < 200 or not backbone_name:
            error_message = """**⚠️ Missing Information**

Please provide:
✓ Plasmid name (e.g., "pEGFP-N1")
✓ Complete plasmid sequence (at least 200 bp, FASTA or raw format)

**Please try again with both pieces of information:**"""
            
            return (
                Result_ProcessUserInput(
                    status="error",
                    response=error_message,
                ),
                CustomBackboneNameAndSequence,
            )
        
        # Success - sequence extracted
        return (
            Result_ProcessUserInput(
                status="success",
                result=response,
                response="",
            ),
            GeneInsertChoice,
        )


class CustomBackboneNameOnly(BaseUserInputState):
    """State for collecting custom plasmid backbone name only.
    
    User provides just the plasmid name - we'll attempt to look up the sequence.
    """
    prompt_process = """Please act as an expert in plasmid design. Given the user input with a plasmid name, extract the name and prepare for sequence lookup.

User Input: {user_message}

Return JSON:
{{
  "BackboneName": "extracted plasmid name",
  "Reasoning": "explanation of what was extracted"
}}"""
    
    request_message = PROMPT_REQUEST_BACKBONE_NAMEONLY

    @classmethod
    def step(cls, user_message, **kwargs):
        """Process custom backbone name input and attempt lookup.
        
        Args:
            user_message: User's plasmid name
            **kwargs: Additional context from workflow
            
        Returns:
            Tuple of (Result_ProcessUserInput, next_state)
                - Routes to GeneInsertChoice on success
                - Routes back on error if name not recognized
        """
        prompt = cls.prompt_process.format(user_message=user_message)
        response = OpenAIChat.chat(prompt, use_GPT4=True)

        backbone_name = response.get("BackboneName", "").strip()
        
        if not backbone_name:
            error_message = """**⚠️ Plasmid Name Required**

We could not extract a plasmid name from your input.

**Please provide:**
- The plasmid name (e.g., "pEGFP-N1", "pUC19", "pcDNA3.1")

**Please try again:**"""
            
            return (
                Result_ProcessUserInput(
                    status="error", 
                    response=error_message,
                ),
                CustomBackboneNameOnly,
            )
        
        # Try Biomni lookup
        biomni_agent = get_biomni_agent()
        if biomni_agent is not None:
            logger.info(f"Attempting Biomni lookup for plasmid: {backbone_name}")
            
            found_backbone_sequence = False
            for attempt in range(3):
                try:
                    biomni_result = biomni_agent.lookup_plasmid_by_name(backbone_info=response)
                    
                    # Parse successful result
                    if isinstance(biomni_result, dict):
                        biomni_response = biomni_result.get("response_data", [])
                        if biomni_response:
                            match = re.search(r"<solution>\s*(\{.*?\})\s*</solution>", biomni_response[-1], re.DOTALL)
                            if match:
                                json_str = match.group(1)
                                data = json.loads(json_str)
                                sequence_extracted = data.get("full_dna_sequence", "")
                                
                                if sequence_extracted and len(sequence_extracted) > 200:
                                    found_backbone_sequence = True
                                    response["SequenceExtracted"] = sequence_extracted
                                    response["SequenceLength"] = len(sequence_extracted)
                                    break
                    
                    if not found_backbone_sequence and attempt < 2:
                        time.sleep(1)
                        
                except Exception as e:
                    logger.warning(f"Biomni lookup attempt {attempt + 1} failed: {e}")
                    if attempt < 2:
                        time.sleep(1)
                
            if not found_backbone_sequence:
                error_message = f"""**⚠️ Plasmid Not Found**

Could not find sequence information for plasmid: **{backbone_name}**

**Options:**
1. Go back and select from our library (pcDNA3.1(+) or pAG)
2. Provide both the name AND sequence (option 2)
3. Describe what type of backbone you need (option 4)

Would you like to try a different plasmid name, or select another option?"""
                
                return (
                    Result_ProcessUserInput(
                        status="error",
                        response=error_message, 
                    ),
                    CustomBackboneNameOnly,
                )
        
        # Success - sequence found
        return (
            Result_ProcessUserInput(
                status="success",
                result=response,
                response="",
            ),
            GeneInsertChoice,
        )


class CustomBackboneDescription(BaseUserInputState):
    """State for collecting custom backbone by description.
    
    User describes what type of backbone they need (promoter, marker, origin, etc.)
    and we either suggest a library option or prepare for custom search.
    """
    prompt_process = PROMPT_PROCESS_CUSTOM_BACKBONE_EXPRESSION
    request_message = PROMPT_REQUEST_BACKBONE_DESCRIPTION

    @classmethod
    def step(cls, user_message, **kwargs):
        """Process user's backbone description and suggest best option.
        
        Args:
            user_message: User's description of ideal backbone
            **kwargs: Additional context from workflow
            
        Returns:
            Tuple of (Result_ProcessUserInput, next_state)
                - Routes to BackboneLibrarySelection if pcDNA3.1(+) or other library sequence match
                - Routes to CustomBackboneNameOnly if custom search needed
                - Routes back if description unclear
        """
        prompt = cls.prompt_process.format(user_message=user_message)
        response = OpenAIChat.chat(prompt, use_GPT4=True)

        backbone_name = response.get('BackboneName', "").strip()

        #If the suggested plasmid matches a library name then go ahead and pull the sequence.
        
        # Load the Library
        plasmid_reader = PlasmidLibraryReader()
        plasmid_reader.load_library()
        sequence_extracted = ""
        backbone_details = plasmid_reader.get_plasmid_sequence_details(backbone_name)
        if not backbone_details.empty:
            sequence_extracted = backbone_details['Sequence']
            response["SequenceExtracted"] = sequence_extracted
            if len(sequence_extracted) > 200:
                logger.info(f"Was able to find {backbone_name} in the plasmid library, taking the sequence from the local repo.")
            
            if pd.isna(response["SequenceExtracted"]) or response["SequenceExtracted"] == '':
                logger.warning(f"Backbone {backbone_name} found but has no sequence in library")
                response["SequenceExtracted"] = None
            

        if not sequence_extracted:
            biomni_agent = get_biomni_agent()
            if biomni_agent is not None:
                logger.info(f"Attempting Biomni lookup for plasmid: {backbone_name}")
                
                found_backbone_sequence = False
                for attempt in range(3):
                    biomni_result = biomni_agent.lookup_plasmid_by_name(backbone_info=response)
                    biomni_response = biomni_result["response_data"]

                    if isinstance(biomni_result, dict) and ("error" in biomni_result.keys()):
                        logger.warning(f"Biomni lookup attempt {attempt + 1} failed: {biomni_result.get('error')}")
                        if attempt < 2:
                            time.sleep(1)
                            continue
                    else:
                        # Parse successful result
                        if isinstance(biomni_result, dict):
                            match = re.search(r"<solution>\s*(\{.*?\})\s*</solution>", biomni_response[-1], re.DOTALL)
                            if match:
                                json_str = match.group(1)
                                data = json.loads(json_str)
                                sequence_extracted = data.get("full_dna_sequence", "")
                                
                        if sequence_extracted and len(sequence_extracted) > 200:
                            found_backbone_sequence = True
                            response["SequenceExtracted"] = sequence_extracted
                            response["SequenceLength"] = len(sequence_extracted)
                            break
                                
                    
                if not found_backbone_sequence:
                    breakpoint()
                    error_message = f"""**⚠️ Plasmid Not Found**

    Could not find sequence information for plasmid: **{backbone_name}**

    **Please try:**
    1. Check the plasmid name spelling
    2. Provide alternative names or identifiers  
    3. Go back and provide the sequence directly (option 1)

    Please try again with a different plasmid name or identifier:"""
                    
                    return (
                        Result_ProcessUserInput(
                            status="error",
                            response=error_message, 
                        ),
                        CustomBackboneDescription,
                    )

        # Success - route based on whether Biomni suggested the plasmid
        if response.get("PlasmidSuggested"):
            next_state = ConfirmPlasmidBackboneChoice
        else:
            next_state = GeneInsertChoice
    
        backbone_prompt = PROMPT_REQUEST_CONFIRM_BACKBONE_CHOICE.format(
            BackboneName=response.get("BackboneName", "Backbone Not Found"),
            Promoter=response.get("Promoter", "Promoter Not Specified"),
            SelectionMarker=response.get("SelectionMarker", "Selection Marker Not Specified"),
            Origin=response.get("Origin", "Origin Not Specified"),
        )
        return (
            Result_ProcessUserInput(
                status="success",
                result=response,
                response=backbone_prompt,
            ),
            next_state,
        )


"""
class StateStep1Backbone(BaseUserInputState):
    """#Legacy state - now replaced by BackboneSelectionChoice and sub-states.
    
    #This state is kept for backward compatibility but is no longer used in the main flow.
    """
    prompt_process = PROMPT_PROCESS_STEP1_BACKBONE_INQUIRY_EXPRESSION
    request_message = PROMPT_REQUEST_STEP1_INQUIRY_EXPRESSION

    @classmethod
    def step(cls, user_message, **kwargs):
        """#Legacy step method.
        """
        # This state should not be reached in normal workflow
        return (
            Result_ProcessUserInput(
                status="success",
                result={},
                response="",
            ),
            GeneInsertChoice,
        )
"""
"""
class CustomBackboneSequenceInput(BaseUserInputState):
    """#State for collecting custom plasmid backbone sequence directly.
    
    #Asks user to provide the complete plasmid backbone sequence in FASTA or GenBank format.
    """
    prompt_process = PROMPT_PROCESS_CUSTOM_BACKBONE_EXPRESSION
    request_message = """#Please provide your complete plasmid backbone sequence.

#**Accepted formats:**
#- FASTA format: >plasmid_name followed by sequence
#- GenBank format: LOCUS line followed by sequence
#- Raw sequence: Just the DNA sequence (ATGC...)

#**Example:**
#```
#>pCustomVector
#ATGCGATCGATCG...
#```

Please paste your sequence below:"""

    @classmethod
    def step(cls, user_message, **kwargs):
        """Process custom backbone sequence input."""

        prompt = cls.prompt_process.format(user_message=user_message)
        response = OpenAIChat.chat(prompt, use_GPT4=True)

        sequence_provided = response.get("SequenceProvided", False)
        sequence_extracted = response.get("SequenceExtracted", "")
        
        if not sequence_provided or not sequence_extracted or len(sequence_extracted) < 200:
            error_message = """#**⚠️ Sequence Issue**

#We couldn't extract a valid plasmid sequence from your input.

#**Please ensure:**
#- The sequence contains only DNA bases (A, T, G, C)
#- The sequence is at least 200 base pairs long
#- Use FASTA format (>name followed by sequence) for best results

#Please try again with your complete plasmid sequence.
"""
            
            return (
                Result_ProcessUserInput(
                    status="error",
                    response=error_message,
                ),
                CustomBackboneSequenceInput,
            )
        
        # Success - sequence extracted
        return (
            Result_ProcessUserInput(
                status="success",
                result=response,
                response="",
            ),
            GeneInsertChoice,
        )
"""
"""
class CustomBackboneDetailsInput(BaseUserInputState):
    """#State for collecting custom plasmid backbone details for sequence lookup.
    
    #Asks user to provide plasmid name and details for Biomni sequence lookup.
    """
    prompt_process = PROMPT_PROCESS_CUSTOM_BACKBONE_EXPRESSION  
    request_message = """#Please provide your plasmid backbone details for sequence lookup.

#**Required information:**
#- **Plasmid name** (e.g., "pEGFP-N1", "pUC19", "pcDNA3.1")

#**Optional but helpful:**
#- Promoter type (e.g., CMV, SV40, T7)
#- Selection marker (e.g., Ampicillin, Neomycin, Kanamycin)
#- Origin of replication (e.g., pBR322, ColE1)

#**Example:**
#"pEGFP-N1 with CMV promoter, Kanamycin resistance, pBR322 origin"
#or
#"Select a backbone for transient constitutive expression in HEK293 Cells"

#Please provide your plasmid details:
"""

    @classmethod  
    def step(cls, user_message, **kwargs):
        """Process custom backbone details and attempt sequence lookup."""
        # This will use the same logic as the current CustomBackboneInput
        # but with the expectation that user provided name/details not sequence

        prompt = cls.prompt_process.format(user_message=user_message)
        response = OpenAIChat.chat(prompt, use_GPT4=True)

        backbone_name = response.get("BackboneName", "").strip()
        sequence_extracted = response.get("SequenceExtracted", "")
        
        if not backbone_name:
            error_message = """#**⚠️ Plasmid Name Required**

#We could not identify a plasmid that fit your request. Please provide additional details or a specific plasmid name.

#**Please provide:**
#- The plasmid name (e.g., "pEGFP-N1", "pUC19")
#- Any additional details you know

#Please try again with the plasmid name or a better detailed description:
"""
            
            return (
                Result_ProcessUserInput(
                    status="error", 
                    response=error_message,
                ),
                CustomBackboneDetailsInput,
            )
        
        # Try Biomni lookup logic (similar to existing CustomBackboneInput)
        biomni_agent = get_biomni_agent()
        if biomni_agent is not None:
            logger.info(f"Attempting Biomni lookup for plasmid: {backbone_name}")
            
            found_backbone_sequence = False
            for attempt in range(3):
                sequence_extracted = ""
                biomni_result = biomni_agent.lookup_plasmid_by_name(backbone_info=response)
                biomni_response = biomni_result["response_data"]

                if isinstance(biomni_result, dict) and ("error" in biomni_result.keys()):
                    logger.warning(f"Biomni lookup attempt {attempt + 1} failed: {biomni_result.get('error')}")
                    if attempt < 2:
                        time.sleep(1)
                        continue
                else:
                    # Parse successful result
                    if isinstance(biomni_response[-1], str) or isinstance(biomni_result, dict):
                        match = re.search(r"<solution>\s*(\{.*?\})\s*</solution>", biomni_response[-1], re.DOTALL)
                        if match:
                            json_str = match.group(1)
                            data = json.loads(json_str)
                            sequence_extracted = data.get("full_dna_sequence", "")
                            
                    if sequence_extracted and len(sequence_extracted) > 200:
                        found_backbone_sequence = True
                        response["SequenceExtracted"] = sequence_extracted
                        response["SequenceLength"] = len(sequence_extracted)
                        break
                            
                
            if not found_backbone_sequence:
                error_message = f"""**⚠️ Plasmid Not Found**

Could not find sequence information for plasmid: **{backbone_name}**

**Please try:**
1. Check the plasmid name spelling
2. Provide alternative names or identifiers  
3. Go back and provide the sequence directly (option 1)
4. If you are confident your prompt should work please providing the description again (sometimes it will work if given more opportunities)
"""
                
                return (
                    Result_ProcessUserInput(
                        status="error",
                        response=error_message, 
                    ),
                    CustomBackboneDetailsInput,
                )
        
        # Success - route based on whether Biomni suggested the plasmid
        if response.get("PlasmidSuggested"):
            next_state = ConfirmPlasmidBackboneChoice
        else:
            next_state = GeneInsertChoice
            
        return (
            Result_ProcessUserInput(
                status="success",
                result=response,
                response="",
            ),
            next_state,
        )
"""

class ConfirmPlasmidBackboneChoice(BaseUserInputState):
    """State for confirming plasmid backbone choice suggested by Biomni.
    
    Displays the suggested plasmid backbone name and asks user to confirm
    or provide a different plasmid name/sequence.
    """

    prompt_process = PROMPT_PROCESS_CONFIRM_BACKBONE_CHOICE
    #request_message = PROMPT_REQUEST_CONFIRM_BACKBONE_CHOICE

    @classmethod
    def step(cls, user_message, **kwargs):
        """Process user confirmation of suggested plasmid backbone.
        
        If user confirms the suggested backbone, proceed to gene insert selection.
        If user wants to provide a different backbone, route back to CustomBackboneInput.
        
        Args:
            user_message: User's confirmation/modification response
            **kwargs: Additional context from workflow including memory
        
        Returns:
            Tuple of (Result_ProcessUserInput, next_state)
                - Routes to BackboneSelectionChoice if user wants to change backbone
                - Routes to GeneInsertChoice if user confirms backbone
        """
        memory = kwargs.get("memory", {})
        
        # Extract backbone data from memory (could be from any of the 4 backbone selection paths)
        custom_backbone_result = (memory.get("BackboneLibrarySelection") or 
                                   memory.get("CustomBackboneNameAndSequence") or 
                                   memory.get("CustomBackboneNameOnly") or 
                                   memory.get("CustomBackboneDescription"))
        backbone_result = memory.get("BackboneSelectionChoice") 
        
        # Default values in case data is missing
        backbone_name = "Unknown"
        promoter = "Not specified"
        selection_marker = "Not specified" 
        origin = "Not specified"
        
        # Extract backbone details from memory
        if custom_backbone_result and custom_backbone_result.result:
            backbone_data = custom_backbone_result.result
            backbone_name = backbone_data.get("BackboneName", "Custom Backbone")
            promoter = backbone_data.get("Promoter", "Not specified")
            selection_marker = backbone_data.get("SelectionMarker", "Not specified")
            origin = backbone_data.get("Origin", "Not specified")
        elif backbone_result and backbone_result.result:
            backbone_data = backbone_result.result
            backbone_name = backbone_data.get("BackboneName", "Selected Backbone")
            # For standard backbones, we might not have detailed features
            promoter = backbone_data.get("Promoter", "Standard promoter")
            selection_marker = backbone_data.get("SelectionMarker", "Standard marker")
            origin = backbone_data.get("Origin", "Standard origin")

        # Use formatted_request as the message to the user (e.g., in UI or as part of LLM response)
        prompt = cls.prompt_process.format(user_message=user_message)
        response = OpenAIChat.chat(prompt, use_GPT4=True)

        status = response.get("Status", "").lower()
        if "modify" in status or "change" in status:
            next_state = BackboneSelectionChoice
        else:
            next_state = GeneInsertChoice

        return (
            Result_ProcessUserInput(
                status="success",
                result=response,
                response="",  # Show the filled-out confirmation message to the user
            ),
            next_state,
        )


class GeneInsertChoice(BaseUserInputState):
    """State for choosing how to provide gene insert information.
    
    Presents numbered options for providing gene insert:
    1. I have the exact DNA sequence  
    2. I have the gene name for lookup
    """
    prompt_process = """Please act as an expert in molecular biology. Given the user input, determine which option they selected for providing gene insert information.

User message: {user_message}

The user is choosing between:
1. Providing the exact DNA sequence directly
2. Providing gene name for sequence lookup

Return JSON with:
{{
  "Choice": "1" or "2", 
  "Reasoning": "explanation of which option the user selected",
  "Status": "success"
}}"""
    
    request_message = """
    
Now let's specify your gene insert.

How would you like to provide the gene information?

1. **I have the exact DNA sequence** - Paste the coding sequence directly
2. **I have the gene name** - Provide gene name for automatic sequence lookup

Please select **1** or **2**."""

    @classmethod
    def step(cls, user_message, **kwargs):
        """Process user's choice for gene insert input method.
        
        Routes to appropriate gene input method based on selection.
        
        Args:
            user_message: User's choice (1 or 2)
            **kwargs: Additional context from workflow
            
        Returns:
            Tuple of (Result_ProcessUserInput, next_state)
                - Routes to GeneSequenceInput if choice 1
                - Routes to GeneNameInput if choice 2
        """
        prompt = cls.prompt_process.format(user_message=user_message)
        response = OpenAIChat.chat(prompt, use_GPT4=True)
        
        choice = response.get("Choice", "").strip()
        reasoning = response.get("Reasoning", "")
        
        if choice == "1":
            next_state = GeneSequenceInput
        elif choice == "2":
            next_state = GeneNameInput
        else:
            # Default to name input if unclear
            next_state = GeneNameInput
        
        return (
            Result_ProcessUserInput(
                status="success",
                result=response,
                response="",
            ),
            next_state,
        )


class GeneSequenceInput(BaseUserInputState):
    """State for collecting exact gene sequence from user."""
    prompt_process = PROMPT_PROCESS_AGENT1
    request_message = """Please provide your exact gene sequence.

**Accepted formats:**
- FASTA format: >gene_name followed by sequence  
- Raw sequence: Just the DNA sequence (ATGC...)

**Example:**
```
>EGFP
ATGGTGAGCAAGGGCGAG...
```

Please paste your gene sequence below:"""

    @classmethod
    def step(cls, user_message, **kwargs):
        """Process gene sequence input."""
        prompt = cls.prompt_process.format(user_message=user_message)
        response = OpenAIChat.chat(prompt, use_GPT4=True)
        response["original_request"] = user_message
        
        has_sequence = response.get("Has exact sequence", "no").lower() == "yes"
        
        if not has_sequence:
            error_message = """**⚠️ No Sequence Detected**

We couldn't find a valid DNA sequence in your input.

**Please ensure:**
- Use DNA bases only (A, T, G, C)
- Provide sequence in FASTA format or as raw sequence
- Sequence should be the coding sequence (CDS) for your gene

Please try again with your gene sequence:"""
            
            return (
                Result_ProcessUserInput(
                    status="error",
                    response=error_message,
                ),
                GeneSequenceInput,
            )
        
        text_response = ""
        
        return (
            Result_ProcessUserInput(
                status="success",
                result=response,
                response=text_response,
            ),
            ConstructConfirmation,
        )


class GeneNameInput(BaseUserInputState):
    """State for collecting gene name for sequence lookup."""
    prompt_process = PROMPT_PROCESS_AGENT1
    request_message = """
    
**📝 Please provide the gene name for sequence lookup: 📝**

**Examples:**
- "EGFP" or "Enhanced Green Fluorescent Protein"
- "human TP53" or "mouse Actb" 
- "mCherry" or "Luciferase"

**Tips:**
- Include species if known (e.g., "human", "mouse")
- Use standard gene symbols when possible
- We'll suggest variants if your gene has multiple forms

📝 Please enter your gene name: 📝


**⏳ Please note this step may take a bit longer as we look up the sequence for you. ⏳**"""

    @classmethod
    def step(cls, user_message, **kwargs):
        """Process gene name input and attempt sequence lookup."""
        prompt = cls.prompt_process.format(user_message=user_message)
        response = OpenAIChat.chat(prompt, use_GPT4=True)
        response["original_request"] = user_message
        
        has_sequence = response.get("Has exact sequence", "no").lower() == "yes"
        
        if has_sequence:
            # User actually provided a sequence, redirect to sequence processing
            text_response = ""
            
            return (
                Result_ProcessUserInput(
                    status="success",
                    result=response,
                    response=text_response,
                ),
                ConstructConfirmation,
            )
        
        text_response = ""

        # Use Biomni to look up the gene sequence (existing logic)
        biomni_agent = get_biomni_agent()
        if biomni_agent is not None:
            target_gene = response.get('Target gene')
            sequence_found = False
            gene_sequence = None
            
            # Try to look up target gene (allow 2 attempts)
            for attempt in range(2):
                logger.info(f"Biomni lookup attempt {attempt + 1}/2 for target gene: {target_gene}")
                biomni_result = biomni_agent.lookup_gene_sequence(gene_name=target_gene)
                # Parse biomni output to extract sequence and gene info
                if isinstance(biomni_result, dict):
                    breakpoint()
                    gene_sequence = biomni_result.get("sequence")
                    found_gene_name = biomni_result.get("gene_name")
                    if gene_sequence:
                        sequence_found = True
                        response["GeneSequence"] = gene_sequence
                        response["FoundGeneName"] = found_gene_name
                        logger.info(f"Biomni successfully found sequence for target gene: {target_gene}")
                        break
                else:
                    # Parse JSON from text response
                    match = re.search(r"<solution>\s*(\{.*?\})\s*</solution>", biomni_result[-1] if isinstance(biomni_result, list) else biomni_result, re.DOTALL)
                    if match:
                        json_str = match.group(1)
                        data = json.loads(json_str)
                        gene_sequence = data.get("sequence")
                        found_gene_name = data.get("gene_name")
                        if gene_sequence:
                            sequence_found = True
                            response["GeneSequence"] = gene_sequence
                            response["FoundGeneName"] = found_gene_name
                            logger.info(f"Biomni successfully found sequence for target gene: {target_gene}")
                            break
                
                if not sequence_found and attempt < 1:
                    time.sleep(1)  # Wait before retrying
            
            if not sequence_found:
                logger.warning("Biomni could not find gene sequence for target gene or any suggested variants")
                error_response = f"**❌ Gene Lookup Failed**\n\n"
                error_response += f"Could not find sequence information for **{response.get('Target gene', 'Unknown')}**"
                if response.get("Suggested variants"):
                    variants_str = response.get('Suggested variants')
                    if isinstance(variants_str, list):
                        variants_str = ", ".join(variants_str)
                    error_response += f" or suggested variants (**{variants_str}**)"
                error_response += ".\n\n**Please try again with:**\n"
                error_response += "- A more specific gene name\n"
                error_response += "- The exact DNA sequence (go back to option 1)\n"
                error_response += "- Alternative gene names or identifiers"
                
                return (
                    Result_ProcessUserInput(
                        status="error",
                        result=response,
                        response=error_response,
                    ),
                    GeneNameInput,
                )
        else:
            logger.warning("Biomni agent not available for gene sequence lookup")
            return (
                Result_ProcessUserInput(
                    status="error",
                    result=response,
                    response="**❌ Gene Lookup Service Unavailable**\n\nThe gene sequence lookup service is currently unavailable.\n\n**Please go back and provide the exact DNA sequence** (option 1) for your gene insert.",
                ),
                GeneInsertChoice,
            )

        # Success - sequence found
        breakpoint()
        return (
            Result_ProcessUserInput(
                status="success",
                result=response,
                response=text_response,
            ),
            ConstructConfirmation,
        )


class GeneInsertSelection(BaseUserInputState):
    """State for collecting gene insert information.
    
    Asks user to provide either:
    1. Exact DNA sequence of the gene insert
    2. Gene name/identifier for sequence lookup
    
    Uses LLM to parse response and determine which path to take.
    """
    prompt_process = PROMPT_PROCESS_AGENT1
    request_message = PROMPT_REQUEST_AGENT1

    @classmethod
    def step(cls, user_message, **kwargs):
        """Process gene insert input (sequence or gene identifier).
        
        Parses user input to determine if they provided an exact sequence
        or a gene name for lookup. Stores original input for later sequence extraction.
        
        Args:
            user_message: User's gene insert input (sequence or gene name)
            **kwargs: Additional context from workflow
            
        Returns:
            Tuple of (Result_ProcessUserInput, next_state)
                - Routes to ConstructConfirmation to show design summary
        """
        prompt = cls.prompt_process.format(user_message=user_message)
        response = OpenAIChat.chat(prompt, use_GPT4=True)
        response["original_request"] = user_message
        
        has_sequence = response.get("Has exact sequence", "no").lower() == "yes"
        
        if has_sequence:
            # User provided exact sequence, proceed directly
            text_response = ""
        else:
            # User provided gene name, agents will look it up
            text_response = ""

            # Use Biomni to look up the gene sequence
            biomni_agent = get_biomni_agent()
            if biomni_agent is not None:
                target_gene = response.get('Target gene')
                sequence_found = False
                gene_sequence = None
                
                # Try to look up target gene (allow 2 attempts)
                for attempt in range(2):
                    try:
                        logger.info(f"Biomni lookup attempt {attempt + 1}/2 for target gene: {target_gene}")
                        biomni_result = biomni_agent.lookup_gene_sequence(gene_name=target_gene)
                        
                        # Parse biomni output to extract sequence and gene info
                        if isinstance(biomni_result, dict):
                            gene_sequence = biomni_result.get("sequence")
                            found_gene_name = biomni_result.get("gene_name")
                            if gene_sequence:
                                sequence_found = True
                                response["GeneSequence"] = gene_sequence
                                response["FoundGeneName"] = found_gene_name
                                logger.info(f"Biomni successfully found sequence for target gene: {target_gene}")
                                break
                        else:
                            # Parse JSON from text response
                            match = re.search(r"<solution>\s*(\{.*?\})\s*</solution>", biomni_result[-1] if isinstance(biomni_result, list) else biomni_result, re.DOTALL)
                            if match:
                                json_str = match.group(1)
                                data = json.loads(json_str)
                                gene_sequence = data.get("sequence")
                                found_gene_name = data.get("gene_name")
                                if gene_sequence:
                                    sequence_found = True
                                    response["GeneSequence"] = gene_sequence
                                    response["FoundGeneName"] = found_gene_name
                                    logger.info(f"Biomni successfully found sequence for target gene: {target_gene}")
                                    break
                        
                        if not sequence_found and attempt < 1:
                            time.sleep(1)  # Wait before retrying
                            
                    except Exception as e:
                        logger.warning(f"Biomni lookup attempt {attempt + 1}/2 failed for target gene: {e}")
                        if attempt < 1:
                            time.sleep(1)  # Wait before retrying
                
                # If target gene lookup failed, try suggested variants (allow 2 attempts)
                if not sequence_found and response.get("Suggested variants"):
                    suggested_variants = response.get("Suggested variants")
                    if isinstance(suggested_variants, str):
                        suggested_variants = [suggested_variants]
                    
                    for variant in suggested_variants:
                        for attempt in range(2):
                            try:
                                logger.info(f"Biomni lookup attempt {attempt + 1}/2 for suggested variant: {variant}")
                                biomni_result = biomni_agent.lookup_gene_sequence(gene_name=variant)
                                
                                # Parse biomni output to extract sequence and gene info
                                if isinstance(biomni_result, dict):
                                    gene_sequence = biomni_result.get("sequence")
                                    found_gene_name = biomni_result.get("gene_name")
                                    if gene_sequence:
                                        sequence_found = True
                                        response["GeneSequence"] = gene_sequence
                                        response["FoundGeneName"] = found_gene_name
                                        response["Target gene"] = variant  # Update target gene to the found variant
                                        logger.info(f"Biomni successfully found sequence for suggested variant: {variant}")
                                        break
                                else:
                                    # Parse JSON from text response
                                    match = re.search(r"<solution>\s*(\{.*?\})\s*</solution>", biomni_result[-1] if isinstance(biomni_result, list) else biomni_result, re.DOTALL)
                                    if match:
                                        json_str = match.group(1)
                                        data = json.loads(json_str)
                                        gene_sequence = data.get("sequence")
                                        found_gene_name = data.get("gene_name")
                                        if gene_sequence:
                                            sequence_found = True
                                            response["GeneSequence"] = gene_sequence
                                            response["FoundGeneName"] = found_gene_name
                                            response["Target gene"] = variant  # Update target gene to the found variant
                                            logger.info(f"Biomni successfully found sequence for suggested variant: {variant}")
                                            break
                                
                                if not sequence_found and attempt < 1:
                                    time.sleep(1)  # Wait before retrying
                                    
                            except Exception as e:
                                logger.warning(f"Biomni lookup attempt {attempt + 1}/2 failed for suggested variant {variant}: {e}")
                                if attempt < 1:
                                    time.sleep(1)  # Wait before retrying
                        
                        if sequence_found:
                            break
                
                # Check for gene name mismatch after successful sequence lookup
                if sequence_found and response.get("FoundGeneName"):
                    found_gene_name = response.get("FoundGeneName", "").lower().strip()
                    target_gene_name = response.get("Target gene", "").lower().strip()
                    
                    # Simple semantic match check - you can make this more sophisticated
                    if found_gene_name and target_gene_name and found_gene_name != target_gene_name:
                        # Check if they're not just minor variations (e.g., "gfp" vs "egfp")
                        if not (found_gene_name in target_gene_name or target_gene_name in found_gene_name):
                            logger.info(f"Gene name mismatch detected: requested '{target_gene_name}' but found '{found_gene_name}'")
                            # Route to confirmation state
                            text_response = f"**⚠️ Gene Name Mismatch Detected**\n\n"
                            text_response += f"**You requested:** {response.get('Target gene', 'Unknown')}\n"
                            text_response += f"**Found sequence for:** {response.get('FoundGeneName', 'Unknown')}\n\n"
                            text_response += f"The sequence we found appears to be for a different gene than what you requested. Would you like to proceed with this sequence, or would you prefer to try a different gene name?"
                            
                            return (
                                Result_ProcessUserInput(
                                    status="success",
                                    result=response,
                                    response=text_response,
                                ),
                                ConfirmGeneIdentityMismatch,
                            )
                
                if not sequence_found:
                    logger.warning("Biomni could not find gene sequence for target gene or any suggested variants")
                    error_response = f"**❌ Gene Lookup Failed**\n\n"
                    error_response += f"Could not find sequence information for **{response.get('Target gene', 'Unknown')}**"
                    if response.get("Suggested variants"):
                        variants_str = response.get('Suggested variants')
                        if isinstance(variants_str, list):
                            variants_str = ", ".join(variants_str)
                        error_response += f" or suggested variants (**{variants_str}**)"
                    error_response += ".\n\n**Please try again with:**\n"
                    error_response += "- A more specific gene name\n"
                    error_response += "- The exact DNA sequence\n"
                    error_response += "- Alternative gene names or identifiers"
                    
                    return (
                        Result_ProcessUserInput(
                            status="error",
                            result=response,
                            response=error_response,
                        ),
                        GeneInsertChoice,
                    )
            else:
                logger.warning("Biomni agent not available for gene sequence lookup")
                return (
                    Result_ProcessUserInput(
                        status="error",
                        result=response,
                        response="**❌ Gene Lookup Service Unavailable**\n\nThe gene sequence lookup service is currently unavailable.\n\n**Please provide the exact DNA sequence** for your gene insert.",
                    ),
                    GeneInsertChoice,
                )

            
        text_response = PROMPT_REQUEST_SEQUENCE_VALIDATION.format(gene_name=response.get('FoundGeneName', 'Unknown'))
        return (
            Result_ProcessUserInput(
                status="success",
                result=response,
                response=text_response,
            ),
            ConstructConfirmation,
        )


class ConstructConfirmation(BaseUserInputState):
    """State for displaying construct summary and requesting confirmation.
    
    Shows user a summary of the planned construct with:
    - Gene insert name
    - Plasmid backbone name
    
    Allows user to either proceed to output format selection or modify the gene.
    """
    prompt_process = PROMPT_PROCESS_SEQUENCE_VALIDATION
    #request_message = PROMPT_REQUEST_SEQUENCE_VALIDATION
    request_message = ""

    @classmethod
    def step(cls, user_message, **kwargs):
        """Display construct summary and get user confirmation.
        
        Retrieves gene and backbone data from memory, formats a detailed summary
        message with actual values, and asks user to confirm or modify.
        
        Args:
            user_message: User's confirmation/modification response
            **kwargs: Additional context including memory with previous results
            
        Returns:
            Tuple of (Result_ProcessUserInput, next_state)
                - Routes to GeneInsertChoice if user wants to modify
                - Routes to OutputFormatSelection if user confirms construct
        """
        memory = kwargs.get("memory", {})

        # Extract data from previous states
        gene_result = memory.get("GeneNameInput") or memory.get("GeneSequenceInput")
        backbone_result = memory.get("StateStep1Backbone")
        custom_backbone_result = memory.get("CustomBackboneInput")
        
        breakpoint()
        gene_data = gene_result.result if gene_result else {}
        
        if custom_backbone_result.result:
            backbone_data = custom_backbone_result.result
        elif backbone_result:
            backbone_data = backbone_result.result
        else:
            backbone_data = None
        
        # Extract values
        gene_name = gene_data.get("Target gene", "Unknown") if isinstance(gene_data, dict) else "Unknown"
        backbone_name = backbone_data.get("BackboneName", "Unknown") if isinstance(backbone_data, dict) else "Unknown"
        
        # Format the request_message with actual values for display
        detailed_message = cls.request_message.format(gene_name=gene_name, backbone_name=backbone_name)
        
        # Override request_message temporarily with detailed version
        original_request_message = cls.request_message
        cls.request_message = detailed_message
        
        # Process user response
        prompt = cls.prompt_process.format(user_message=user_message)
        response = OpenAIChat.chat(prompt, use_GPT4=True)

        status = response.get("Status", "").lower()
        if "request_modifications" in status or "modify" in status:
            next_state = GeneInsertChoice
        else:
            # Default to proceeding with output format selection
            next_state = OutputFormatSelection
        
        # Restore original request_message
        cls.request_message = original_request_message
        
        return (
            Result_ProcessUserInput(
                status="success",
                thoughts=response.get("Thoughts", ""),
                result=response,
                response=""  # Empty response to avoid duplication
            ),
            next_state,
        )


class SequenceValidation(BaseUserInputState):
    prompt_process = PROMPT_PROCESS_SEQUENCE_VALIDATION
    request_message = PROMPT_REQUEST_SEQUENCE_VALIDATION

    @classmethod
    def step(cls, user_message, **kwargs):
        memory = kwargs.get("memory", {})
        
        # Extract data from previous states
        gene_result = memory.get("GeneNameInput") or memory.get("GeneSequenceInput")
        backbone_result = memory.get("StateStep1Backbone")
        custom_backbone_result = memory.get("CustomBackboneInput") or memory.get("CustomBackboneDetailsInput")
        
        gene_data = gene_result.result if gene_result else {}
        if custom_backbone_result.result:
            backbone_data = custom_backbone_result.result
        elif backbone_result:
            backbone_data = backbone_result.result
        else:
            backbone_data = None
        
        # Extract values
        gene_name = gene_data.get("Target gene", "Unknown") if isinstance(gene_data, dict) else "Unknown"
        backbone_name = backbone_data.get("BackboneName", "Unknown") if isinstance(backbone_data, dict) else "Unknown"

        
        # Format the request_message with actual values for display
        detailed_message = cls.request_message.format(gene_name=gene_name, backbone_name=backbone_name)
        
        # Override request_message temporarily with detailed version
        original_request_message = cls.request_message
        cls.request_message = detailed_message
        
        # Process user response
        prompt = cls.prompt_process.format(user_message=user_message)
        response = OpenAIChat.chat(prompt, use_GPT4=True)

        status = response.get("Status", "").lower()
        if "request_modifications" in status or "modify" in status:
            next_state = GeneInsertChoice
        else:
            # Default to proceeding with output format selection
            next_state = OutputFormatSelection
        
        # Restore original request_message
        cls.request_message = original_request_message
        
        return (
            Result_ProcessUserInput(
                status="success",
                thoughts=response.get("Thoughts", ""),
                result=response,
                response=""  # Empty response to avoid duplication
            ),
            next_state,
        )


class OutputFormatSelection(BaseUserInputState):
    """State for selecting output format and generating final construct sequence.
    
    Main processing state that:
    1. Gets user's preferred output format (GenBank, FASTA, Raw)
    2. Retrieves gene and backbone sequences
    3. Identifies gene if not named
    4. Looks up backbone in library or uses custom backbone sequence
    5. Intelligently inserts gene into backbone using MCS handler (with optional Biomni)
    6. Formats output in requested format
    7. Displays final construct sequence
    """
    prompt_process = PROMPT_PROCESS_OUTPUT_FORMAT
    request_message = PROMPT_REQUEST_OUTPUT_FORMAT

    @classmethod
    def step(cls, user_message, **kwargs):
        """Process output format selection and generate final construct.
        
        Complex multi-step function that orchestrates the final sequence generation:
        - Parses output format selection (GenBank/FASTA/Raw)
        - Extracts gene sequence from original user input
        - Identifies unnamed genes using LLM
        - Retrieves backbone (standard library or custom)
        - Uses Biomni (if available) or MCSHandler to intelligently insert gene
        - Formats output according to user preference
        
        Args:
            user_message: User's output format selection
            **kwargs: Additional context including memory with all previous results
            
        Returns:
            Tuple of (Result_ProcessUserInput, next_state)
                - Routes to FinalSummary with complete construct sequence
                - Returns errors to GeneInsertChoice if issues occur
        """
        prompt = cls.prompt_process.format(user_message=user_message)
        response = OpenAIChat.chat(prompt, use_GPT4=True)
        
        memory = kwargs.get("memory", {})
        
        # Retrieve stored design information from previous states
        gene_result = memory.get("GeneNameInput") or memory.get("GeneSequenceInput")
        backbone_result = memory.get("StateStep1Backbone")
        custom_backbone_result = memory.get("CustomBackboneInput") or memory.get("CustomBackboneDetailsInput")

        # DO NOT PROVIDE DEFAULTS, Go back to the user if missing.
        breakpoint()
        # Extract result data from Result_ProcessUserInput objects
        gene_data = gene_result.result if gene_result else {}
        if custom_backbone_result.result:
            custom_backbone_data = custom_backbone_result.result
        elif backbone_result:
            backbone_data = backbone_result.result
        else:
            backbone_data = None
        
        # Build final design summary - use custom backbone if available, otherwise standard
        gene_name = gene_data.get("Target gene") if isinstance(gene_data, dict) else "Gene Insert"
        if custom_backbone_data and isinstance(custom_backbone_data, dict):
            # User provided a custom backbone
            backbone_name = custom_backbone_data.get("BackboneName")
            # Get the custom backbone sequence - it could be in either SequenceProvided or SequenceExtracted
            custom_backbone_seq = custom_backbone_data.get("SequenceExtracted")
        else:
            # Standard backbone from StateStep1Backbone
            backbone_name = backbone_data.get("BackboneName") if isinstance(backbone_data, dict) else None
            custom_backbone_seq = None

        selected_format = response.get("Selected Format", "RAW_SEQUENCE").upper()
        
        # Get gene sequence
        input_seq_str = gene_data.get("original_request")
        input_seq_str_remove_ignore = input_seq_str.replace("IGNORE HIPAA RULE", "")
        dna_sequences = re.findall(r"[ACGT]+", input_seq_str_remove_ignore)

        gene_seq = dna = max(dna_sequences, key=len) if dna_sequences else None  # In case any other pieces of text are present, just take the longest continuous sequence of ACGT letters.
        
        if not gene_seq:
                return (
                Result_ProcessUserInput(
                    status="error",
                    response="**❌ Error: No valid DNA sequence found**\n\nPlease provide a DNA sequence in FASTA format or raw ACGT format.",
                ),
                GeneInsertChoice,
            )        
        # Try to identify gene if name is generic/missing
        if gene_name == "Gene Insert" and gene_seq and len(gene_seq) > 50:
            logger.info("Gene name not provided, attempting identification...")
            gene_id_result = GeneIdentifier.identify_gene(gene_seq)
            if gene_id_result and gene_id_result.get("Confidence") in ["high", "medium"]:
                gene_name = f"{gene_id_result.get('Gene Name', 'Gene Insert')} ({gene_id_result.get('Organism', 'Unknown')})"
            else:
                gene_name = "Gene Unidentified"
        
        # Fetch backbone sequence from plasmid library
        plasmid_reader = PlasmidLibraryReader()
        plasmid_reader.load_library()
        # Try to find the plasmid in the library by name, or use custom sequence
        backbone_seq = None
        if custom_backbone_seq:
            # Use the custom backbone sequence provided by user
            backbone_seq = custom_backbone_seq
            logger.info(f"Using custom backbone sequence for {backbone_name}")
        elif backbone_name:
            backbone_details = plasmid_reader.get_plasmid_sequence_details(backbone_name)
            if not backbone_details.empty:
                backbone_seq = backbone_details['Sequence']
                if pd.isna(backbone_seq) or backbone_seq == '':
                    logger.warning(f"Backbone {backbone_name} found but has no sequence in library")
                    backbone_seq = None
        
        if not backbone_seq:
            logger.warning(f"Could not retrieve sequence for backbone: {backbone_name}")
            return (
                Result_ProcessUserInput(
                    status="error",
                    response=f"**❌ Error: Backbone Not Found**\n\nCould not find sequence for backbone **{backbone_name}** in plasmid library.\n\nPlease check the backbone name or select a different option.",
                ),
                StateStep1Backbone,
            )
        
        # Try to use Biomni for intelligent MCS detection if available
        biomni_agent = get_biomni_agent()
        insertion_result = None
        
        if biomni_agent:
            logger.info("Using Biomni for plasmid analysis...")
            try:
                mcs_analysis = biomni_agent.find_mcs_in_plasmid(backbone_seq, backbone_name)
                construct_design = biomni_agent.design_construct(backbone_seq, gene_seq, gene_name)
                
                # If Biomni provides MCS analysis, use it
                if mcs_analysis and "error" not in mcs_analysis:
                    logger.info(f"Biomni analysis: {mcs_analysis}")
                    # Extract insertion info if available
                    insertion_result = MCSHandler.insert_gene_at_mcs(backbone_seq, gene_seq)
                else:
                    # Fall back to standard MCS handler
                    insertion_result = MCSHandler.insert_gene_at_mcs(backbone_seq, gene_seq)
            except Exception as e:
                logger.warning(f"Biomni analysis failed, falling back to standard handler: {e}")
                insertion_result = MCSHandler.insert_gene_at_mcs(backbone_seq, gene_seq)
        else:
            # Fall back to standard MCS handler
            insertion_result = MCSHandler.insert_gene_at_mcs(backbone_seq, gene_seq)
        
        final_seq = insertion_result["final_sequence"]
        insertion_method = insertion_result["method"]
        insertion_position = insertion_result["insertion_position"]
        
        logger.info(f"Gene inserted using method: {insertion_method} at position {insertion_position}")

        
        # Format the output sequence based on user selection
        if selected_format == "FASTA":
            sequence_output = f">Construct ({insertion_method}): {gene_name} in {backbone_name}\n{final_seq}"
        elif selected_format == "GENBANK":
            sequence_output = f"LOCUS   {gene_name.replace(' ', '_')}_in_{backbone_name.replace(' ', '_')} {len(final_seq)} bp\nDEFINITION  Expression construct ({insertion_method})\nSEQUENCE\n{final_seq}\n//"
        else:  # RAW_SEQUENCE
            sequence_output = final_seq
        # Build response message with actual sequence
        import textwrap

        response_message = textwrap.dedent(f"""\
            
            Your construct sequence is ready:

            CONSTRUCT SEQUENCE:
            {sequence_output}

            Design Summary:
            - Gene: {gene_name}
            - Plasmid Backbone: {backbone_name}
            - Total Size: {len(final_seq)} bp
            - Insertion Method: {insertion_method} (at position {insertion_position})
            - Output Format: {selected_format}

            This sequence is ready for synthesis and expression testing.""")

        return (
            Result_ProcessUserInput(
                status="success",
                result={
                    "format": selected_format,
                    "gene_name": gene_name,
                    "backbone": backbone_name,
                    "sequence": final_seq,
                },
                response=response_message,
            ),
            FinalSummary,
        )


class FinalSummary(BaseUserInputState):
    """Final state offering next actions after construct generation.
    
    Presents user with options to:
    1. Download/save the generated construct
    2. Modify the design (go back to gene insert selection)
    3. Start a completely new plasmid design project
    """
    prompt_process = PROMPT_PROCESS_FINAL_SUMMARY
    request_message = PROMPT_REQUEST_FINAL_SUMMARY

    @classmethod
    def step(cls, user_message, **kwargs):
        """Process user's next action choice and route accordingly.
        
        Parses user decision and routes to appropriate next state or terminates workflow.
        
        Args:
            user_message: User's choice for next action
            **kwargs: Additional context from workflow
            
        Returns:
            Tuple of (Result_ProcessUserInput, next_state)
                - Routes to StateEntry if user starts new project
                - Routes to GeneInsertChoice if user wants to modify design
                - Routes to None (ends workflow) if user proceeds with download
        """
        prompt = cls.prompt_process.format(user_message=user_message)
        response = OpenAIChat.chat(prompt, use_GPT4=True)

        next_action = response.get("Next Action", "download_design").lower()
        
        if "start" in next_action or "new" in next_action:
            return (
                Result_ProcessUserInput(
                    status="success", 
                    thoughts=response.get("Thoughts", ""), 
                    result=response,
                    response="Starting new project...",
                ),
                StateEntry,
            )
        elif "modify" in next_action:
            return (
                Result_ProcessUserInput(
                    status="success", 
                    thoughts=response.get("Thoughts", ""), 
                    result=response,
                    response="Let's modify the design...",
                ),
                GeneInsertChoice,
            )
        else:
            return (
                Result_ProcessUserInput(
                    status="success", 
                    thoughts=response.get("Thoughts", ""), 
                    result=response,
                    response="Your construct is ready for ordering!",
                ),
                None,
            )

