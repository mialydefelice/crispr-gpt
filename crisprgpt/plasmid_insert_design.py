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
    
    Displays initial greeting and routes to backbone selection. This state
    does not request user input, only provides the entry prompt.
    """
    request_user_input = False

    @classmethod
    def step(cls, user_message, **kwargs):
        """Display entry message and transition to backbone selection.
        
        Args:
            user_message: Not used at entry point
            **kwargs: Additional context (not used)
            
        Returns:
            Tuple of (Result_ProcessUserInput, next_state)
        """
        return Result_ProcessUserInput(response=PROMPT_REQUEST_ENTRY_EXPRESSION), StateStep1Backbone


class StateStep1Backbone(BaseUserInputState):
    """State for selecting expression plasmid backbone.
    
    Asks user to choose between standard backbones (pcDNA3.1(+), pAG) or provide
    a custom backbone. Uses LLM to parse user response and determine selection.
    """
    prompt_process = PROMPT_PROCESS_STEP1_BACKBONE_INQUIRY_EXPRESSION
    request_message = PROMPT_REQUEST_STEP1_INQUIRY_EXPRESSION

    @classmethod
    def step(cls, user_message, **kwargs):
        """Process backbone selection choice.
        
        Uses LLM to parse user input and identify if they selected a standard
        backbone or want to provide a custom one.
        
        Args:
            user_message: User's backbone selection response
            **kwargs: Additional context from workflow
            
        Returns:
            Tuple of (Result_ProcessUserInput, next_state)
                - Routes to CustomBackboneInput if custom backbone selected
                - Routes to GeneInsertChoice if standard backbone selected
        """
        prompt = cls.prompt_process.format(user_message=user_message)
        response = OpenAIChat.chat(prompt, use_GPT4=True)
        backbone_name = response.get("BackboneName", "").lower()
        
        # Check if user selected a custom backbone option
        if "custom" in backbone_name or response.get("Status", "").lower() == "needs_details":
            # Route to custom backbone choice state first
            next_state = CustomBackboneChoice
        else:
            # Standard backbone selected (pcDNA3.1(+) or pAG)
            next_state = GeneInsertChoice
        
        text_response = f"**Backbone Selection Result**\n\n**Selected Backbone:** {backbone_name}\n\n"
        text_response += f"**Thoughts:** {response.get('Thoughts', 'N/A')}"
        
        return (
            Result_ProcessUserInput(
                status="success",
                thoughts=response.get("Thoughts", ""),
                result=response,
                response=text_response,
            ),
            next_state,
        )


class CustomBackboneChoice(BaseUserInputState):
    """State for choosing how to provide custom backbone information.
    
    Presents numbered options for providing custom plasmid backbone:
    1. I have the complete plasmid sequence
    2. I know the plasmid name/details but need sequence lookup
    """
    prompt_process = """Please act as an expert in plasmid design. Given the user input, determine which option they selected for providing custom backbone information.

User message: {user_message}

The user is choosing between:
1. Providing the complete plasmid sequence directly
2. Providing plasmid name/details for sequence lookup

Return JSON with:
{{
  "Choice": "1" or "2",
  "Reasoning": "explanation of which option the user selected",
  "Status": "success"
}}"""
    
    request_message = """You indicated you want to use a custom plasmid backbone.

How would you like to provide the backbone information?

1. **I have the complete plasmid sequence** - Paste the sequence in FASTA or GenBank format
2. **I know the plasmid name/details** - Provide name and features for sequence lookup

Please select **1** or **2**."""

    @classmethod
    def step(cls, user_message, **kwargs):
        """Process user's choice for custom backbone input method.
        
        Routes to appropriate custom backbone input method based on selection.
        
        Args:
            user_message: User's choice (1 or 2)
            **kwargs: Additional context from workflow
            
        Returns:
            Tuple of (Result_ProcessUserInput, next_state)
                - Routes to CustomBackboneSequenceInput if choice 1
                - Routes to CustomBackboneDetailsInput if choice 2
        """
        prompt = cls.prompt_process.format(user_message=user_message)
        response = OpenAIChat.chat(prompt, use_GPT4=True)
        
        choice = response.get("Choice", "").strip()
        reasoning = response.get("Reasoning", "")
        
        formatted_response = f"**Custom Backbone Method Selected**\n\n**Choice:** {choice}\n\n**Reasoning:** {reasoning}"
        
        if choice == "1":
            next_state = CustomBackboneSequenceInput
        elif choice == "2":
            next_state = CustomBackboneDetailsInput
        else:
            # Default to sequence input if unclear
            next_state = CustomBackboneSequenceInput
            formatted_response += "\n\n*Defaulting to sequence input method.*"
        
        return (
            Result_ProcessUserInput(
                status="success",
                result=response,
                response=formatted_response,
            ),
            next_state,
        )


class CustomBackboneSequenceInput(BaseUserInputState):
    """State for collecting custom plasmid backbone sequence directly.
    
    Asks user to provide the complete plasmid backbone sequence in FASTA or GenBank format.
    """
    prompt_process = PROMPT_PROCESS_CUSTOM_BACKBONE_EXPRESSION
    request_message = """Please provide your complete plasmid backbone sequence.

**Accepted formats:**
- FASTA format: >plasmid_name followed by sequence
- GenBank format: LOCUS line followed by sequence
- Raw sequence: Just the DNA sequence (ATGC...)

**Example:**
```
>pCustomVector
ATGCGATCGATCG...
```

Please paste your sequence below:"""

    @classmethod
    def step(cls, user_message, **kwargs):
        """Process custom backbone sequence input."""
        prompt = cls.prompt_process.format(user_message=user_message)
        response = OpenAIChat.chat(prompt, use_GPT4=True)

        sequence_provided = response.get("SequenceProvided", False)
        sequence_extracted = response.get("SequenceExtracted", "")
        
        if not sequence_provided or not sequence_extracted or len(sequence_extracted) < 200:
            error_message = """**⚠️ Sequence Issue**

We couldn't extract a valid plasmid sequence from your input.

**Please ensure:**
- The sequence contains only DNA bases (A, T, G, C)
- The sequence is at least 200 base pairs long
- Use FASTA format (>name followed by sequence) for best results

Please try again with your complete plasmid sequence."""
            
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
                response=format_json_response(response, "**Custom Backbone Sequence Processed**"),
            ),
            GeneInsertChoice,
        )


class CustomBackboneDetailsInput(BaseUserInputState):
    """State for collecting custom plasmid backbone details for sequence lookup.
    
    Asks user to provide plasmid name and details for Biomni sequence lookup.
    """
    prompt_process = PROMPT_PROCESS_CUSTOM_BACKBONE_EXPRESSION  
    request_message = """Please provide your plasmid backbone details for sequence lookup.

**Required information:**
- **Plasmid name** (e.g., "pEGFP-N1", "pUC19", "pcDNA3.1")

**Optional but helpful:**
- Promoter type (e.g., CMV, SV40, T7)
- Selection marker (e.g., Ampicillin, Neomycin, Kanamycin)
- Origin of replication (e.g., pBR322, ColE1)
- Approximate size (e.g., ~5.4 kb)

**Example:**
"pEGFP-N1 with CMV promoter, Kanamycin resistance, pBR322 origin, approximately 4.7 kb"

Please provide your plasmid details:"""

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
            error_message = """**⚠️ Plasmid Name Required**

We need at least a plasmid name to look up the sequence.

**Please provide:**
- The plasmid name (e.g., "pEGFP-N1", "pUC19")
- Any additional details you know

Please try again with the plasmid name:"""
            
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
                try:
                    biomni_result = biomni_agent.lookup_plasmid_by_name(backbone_info=response)
                    
                    if isinstance(biomni_result, dict) and biomni_result.get("error"):
                        logger.warning(f"Biomni lookup attempt {attempt + 1} failed: {biomni_result.get('error')}")
                        if attempt < 2:
                            time.sleep(1)
                            continue
                    else:
                        # Parse successful result
                        if not isinstance(biomni_result, dict):
                            match = re.search(r"<solution>\s*(\{.*?\})\s*</solution>", biomni_result[-1], re.DOTALL)
                            if match:
                                json_str = match.group(1)
                                data = json.loads(json_str)
                                sequence_extracted = data.get("full_dna_sequence", "")
                                
                        if sequence_extracted and len(sequence_extracted) > 200:
                            found_backbone_sequence = True
                            response["SequenceExtracted"] = sequence_extracted
                            response["SequenceLength"] = len(sequence_extracted)
                            break
                            
                except Exception as e:
                    logger.warning(f"Biomni lookup attempt {attempt + 1} failed: {e}")
                    if attempt < 2:
                        time.sleep(1)
            
            if not found_backbone_sequence:
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
                    CustomBackboneDetailsInput,
                )
        
        # Success - route based on whether Biomni suggested the plasmid
        if response.get("PlasmidSuggested", False):
            next_state = ConfirmPlasmidBackboneChoice
        else:
            next_state = GeneInsertChoice
            
        return (
            Result_ProcessUserInput(
                status="success",
                result=response,
                response=format_json_response(response, "**Custom Backbone Details Processed**"),
            ),
            next_state,
        )


class CustomBackboneInput(BaseUserInputState):
    """State for collecting and validating custom plasmid backbone information.
    
    Asks user to provide custom plasmid backbone details including name and sequence.
    Validates that a sequence was actually provided; if not, shows error and loops
    back to allow retry. Uses LLM to extract backbone name, sequence, and metadata.
    """
    prompt_process = PROMPT_PROCESS_CUSTOM_BACKBONE_EXPRESSION
    request_message = PROMPT_REQUEST_CUSTOM_BACKBONE_EXPRESSION

    @classmethod
    def step(cls, user_message, **kwargs):
        """Process custom backbone input and validate sequence extraction.
        
        Attempts to extract plasmid name, sequence, and features from user input.
        If user provides requirements instead of a name (e.g., "mammalian expression plasmid 
        with constitutive promoter"), uses Biomni to recommend and select an appropriate backbone.
        If sequence extraction fails, displays helpful error message and loops back
        to allow user to retry with sequence included.
        
        Args:
            user_message: User's custom backbone description/sequence/requirements
            **kwargs: Additional context from workflow
            
        Returns:
            Tuple of (Result_ProcessUserInput, next_state)
                - Loops back to CustomBackboneInput if sequence missing (with error)
                - Routes to GeneInsertChoice if sequence successfully extracted/selected
        """
        prompt = cls.prompt_process.format(user_message=user_message)
        response = OpenAIChat.chat(prompt, use_GPT4=True)

        # Check if a sequence was actually provided
        sequence_provided = response.get("SequenceProvided")
        sequence_extracted = response.get("SequenceExtracted")
        backbone_name = response.get("BackboneName").strip()
        
        
        if not sequence_provided and not sequence_extracted:
            # For following steps use Biomni
            biomni_agent = get_biomni_agent()
            if biomni_agent is not None:
                logger.info("Biomni agent available for custom backbone processing")
            else:
                # TODO: Add an error here and exit back to user input
                logger.warning("Biomni agent not available for backbone selection from requirements")
            
            # Get backbone name if not provided and not extracted in the intial prompt step with OpenAI.

            if not backbone_name:
                # User provided requirements, use Biomni to select appropriate backbone
                logger.info(f"User provided backbone requirements instead of plasmid name: {user_message}, will attempt to use Biomni to select backbone.")

                try:
                    # Use Biomni to select appropriate backbone
                    # Have not hit this case yet.
                    biomni_result = biomni_agent.select_backbone_from_user_input(user_input=user_message, response=response)
                    backbone_name = biomni_result.get("BackboneName", "")

                    if backbone_name:
                        response['PlasmidSuggested'] = True

                    if not biomni_result.get("error"):
                        logger.info(f"Biomni successfully selected backbone to match requirements: {biomni_result.get('BackboneName')}")
                        # After Biomni selects backbone, ask user to confirm and provide sequence
                        confirmation_message = f"""Great! Based on your requirements, I've identified an appropriate plasmid backbone.""" 
                        
                    else:
                        logger.warning(f"Biomni could not select backbone: {biomni_result.get('error')}")
                except Exception as e:
                    logger.warning(f"Biomni backbone selection failed: {e}. Falling back to manual entry.")
                    

            if backbone_name != "":
                # Now that we have a normalized backbone name, try to look up the sequence in the sequence library first.

                # Import the library and look for exact matches there first.
                logger.info(f"User provided a backbone name, or one was selected for them given their requirements: {backbone_name}. Attempting to look up sequence...")
                #Try to look up the plasmid by name using Biomni
                found_backbone_sequence = False
                num_attempts = 0
                max_attempts = 3
                for _ in range(max_attempts):
                    if found_backbone_sequence is False and num_attempts < (max_attempts):
                        # Use Biomni to look up plasmid by name
                        biomni_result = biomni_agent.lookup_plasmid_by_name(backbone_info=response)
                        # Increment the attempt counter
                        num_attempts += 1

                        #Actually need to check for errors up here.
                        if type(biomni_result) == dict:
                            if biomni_result.get("error"):
                                logger.warning(f"Biomni lookup attempt {num_attempts} failed with error: {biomni_result.get('error')}")
                                time.sleep(1)  # Wait a bit before retrying
                                continue  # Retry
                        else:
                            # Parse biomni output to a json dict
                            match = re.search(r"<solution>\s*(\{.*?\})\s*</solution>", biomni_result[-1], re.DOTALL)
                            if not match:
                                raise ValueError("No <solution> JSON block found")
                            json_str = match.group(1)
                            data = json.loads(json_str)

                            # Pull out the DNA sequence
                            sequence_extracted = data.get("full_dna_sequence")
                            sequence_length = len(sequence_extracted)
                            # Validate sequence format
                            is_valid_sequence = False
                            if re.fullmatch(r'[ACGTNacgtn]+', sequence_extracted):
                                is_valid_sequence = True
                            
                            if sequence_length > 0 and sequence_length > 200 and is_valid_sequence:
                                found_backbone_sequence = True
                                response["SequenceExtracted"] = sequence_extracted
                                response["SequenceLength"] = sequence_length
                        
                                logger.info(f"Biomni successfully looked up backbone: {response.get('BackboneName')}")
                                confirmation_message = f"""Great! I've found the plasmid backbone '{response.get('BackboneName')}'."""

            else:
                # Have not verified this case yet.
                logger.warning(f"A backbone was not retrieved given the user input. Please try again.")
                # If user did not provide a plasmid name, but provided requirements instead, try to use Biomni to select appropriate backbone.

                error_message = """**⚠️ Sequence Extraction Failed**

We weren't able to extract a plasmid sequence from your input. 

**To use a custom backbone, please provide:**
1. The plasmid name/identifier
2. The actual DNA sequence (in FASTA or raw ACGT format)

**You can also try:**
- Providing the sequence from a GenBank file
- Pasting the sequence from a plasmid repository
- Going back to select a standard backbone (**pcDNA3.1(+)** or **pAG**)

Please try again with the sequence included."""
                
                return (
                    Result_ProcessUserInput(
                        status="error",
                        response=error_message,
                    ),
                    CustomBackboneInput,  # Allow user to try again
            )
        # Sequence was provided, proceed to next state
        else:
            logger.info(f"Edge case: User provided sequence for custom backbone: {backbone_name}, should not be encountering this condition in this state.")

        # Store the backbone data in result so it gets saved to memory with state name "CustomBackboneInput"
        # This ensures the sequence and other details are available downstream

        plasmid_suggested = response.get("PlasmidSuggested", False)

        if plasmid_suggested and len(sequence_extracted)>200:
            next_state = ConfirmPlasmidBackboneChoice
            status = "success"
        elif len(sequence_extracted)<=200:
            # Sequence too short, go back to CustomBackboneInput to get full sequence
            # This should actually be another state to confirm the backbone selection and re-request the sequence.
            status = "error"
            next_state = CustomBackboneInput
        else:
            # plasmid_suggested is False or sequence length > 200 (normal case)
            status = "success"
            next_state = GeneInsertChoice
        
        return (
            Result_ProcessUserInput(
                status=status,
                result=response,  # This will be saved to memory["CustomBackboneInput"]
                response=format_json_response(response, "**Custom Backbone Data**"),
            ),
            next_state,
        )

class ConfirmPlasmidBackboneChoice(BaseUserInputState):
    """State for confirming plasmid backbone choice suggested by Biomni.
    
    Displays the suggested plasmid backbone name and asks user to confirm
    or provide a different plasmid name/sequence.
    """
    prompt_process = PROMPT_PROCESS_CONFIRM_BACKBONE_CHOICE
    request_message = PROMPT_REQUEST_CONFIRM_BACKBONE_CHOICE

    @classmethod
    def step(cls, user_message, **kwargs):
        """Process user confirmation of suggested plasmid backbone.
        
        If user confirms the suggested backbone, proceed to gene insert selection.
        If user wants to provide a different backbone, route back to CustomBackboneInput.
        
        Args:
            user_message: User's confirmation/modification response
            **kwargs: Additional context from workflow
            
        Returns:
            Tuple of (Result_ProcessUserInput, next_state)
                - Routes to CustomBackboneInput if user wants to change backbone
                - Routes to GeneInsertChoice if user confirms backbone
        """
        prompt = cls.prompt_process.format(user_message=user_message)
        response = OpenAIChat.chat(prompt, use_GPT4=True)

        status = response.get("Status", "").lower()
        if "modify" in status or "change" in status:
            next_state = CustomBackboneInput
        else:
            next_state = GeneInsertChoice
        
        return (
                Result_ProcessUserInput(
                    status="success",
                    result=response,  # This will be saved to memory["CustomBackboneInput"]
                    response=format_json_response(response, "**Backbone Confirmation**"),
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
    
    request_message = """Now let's specify your gene insert.

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
        
        formatted_response = f"**Gene Insert Method Selected**\n\n**Choice:** {choice}\n\n**Reasoning:** {reasoning}"
        
        if choice == "1":
            next_state = GeneSequenceInput
        elif choice == "2":
            next_state = GeneNameInput
        else:
            # Default to name input if unclear
            next_state = GeneNameInput
            formatted_response += "\n\n*Defaulting to gene name lookup method.*"
        
        return (
            Result_ProcessUserInput(
                status="success",
                result=response,
                response=formatted_response,
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
        
        text_response = f"**Gene Sequence Processed**\n\n**Target Gene:** {response.get('Target gene', 'Unknown')}\n\n**Sequence:** ```{response.get('Sequence provided', 'N/A')}```"
        
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
    request_message = """Please provide the gene name for sequence lookup.

**Examples:**
- "EGFP" or "Enhanced Green Fluorescent Protein"
- "human TP53" or "mouse Actb" 
- "mCherry" or "Luciferase"

**Tips:**
- Include species if known (e.g., "human", "mouse")
- Use standard gene symbols when possible
- We'll suggest variants if your gene has multiple forms

Please enter your gene name:"""

    @classmethod
    def step(cls, user_message, **kwargs):
        """Process gene name input and attempt sequence lookup."""
        prompt = cls.prompt_process.format(user_message=user_message)
        response = OpenAIChat.chat(prompt, use_GPT4=True)
        response["original_request"] = user_message
        
        has_sequence = response.get("Has exact sequence", "no").lower() == "yes"
        
        if has_sequence:
            # User actually provided a sequence, redirect to sequence processing
            text_response = f"**Gene Sequence Detected**\n\n**Target Gene:** {response.get('Target gene', 'Unknown')}\n\n**Sequence:** ```{response.get('Sequence provided', 'N/A')}```"
            
            return (
                Result_ProcessUserInput(
                    status="success",
                    result=response,
                    response=text_response,
                ),
                ConstructConfirmation,
            )
        
        # Gene name provided - attempt lookup
        text_response = f"**Gene Lookup Initiated**\n\n**Target Gene:** {response.get('Target gene', 'Unknown')}\n\n**Status:** Looking up sequence..."
        if response.get("Suggested variants"):
            variants_str = response.get('Suggested variants')
            if isinstance(variants_str, list):
                variants_str = ", ".join(variants_str)
            text_response += f"\n\n**Suggested Variants:** {variants_str}"

        # Use Biomni to look up the gene sequence (existing logic)
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
            text_response = f"**Gene Insert Information**\n\n**Target Gene:** {response.get('Target gene', 'Unknown')}\n\n**Sequence:** ```{response.get('Sequence provided', 'N/A')}```"
        else:
            # User provided gene name, agents will look it up
            text_response = f"**Gene Insert Information**\n\n**Target Gene:** {response.get('Target gene', 'Unknown')}\n\n**Status:** We will look up the sequence for you."
            if response.get("Suggested variants"):
                variants_str = response.get('Suggested variants')
                if isinstance(variants_str, list):
                    variants_str = ", ".join(variants_str)
                text_response += f"\n\n**Suggested Variants:** {variants_str}"

            # Use Biomni to look up the gene sequence
            breakpoint()
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

            
        
        return (
            Result_ProcessUserInput(
                status="success",
                result=response,
                response=text_response,
            ),
            ConstructConfirmation,
        )


class ConfirmGeneIdentityMismatch(BaseUserInputState):
    """State for confirming gene identity when there's a mismatch between requested and found gene names.
    
    This state is triggered when the gene lookup service returns a sequence for a gene that
    appears to have a different name than what the user requested. Asks user to confirm
    whether they want to proceed with the found sequence or try again with a different name.
    """
    prompt_process = """
You are helping a user confirm whether to proceed with a gene sequence that may not match their original request.

The user requested one gene name, but the sequence lookup service found a sequence for what appears to be a different gene.

User message: {user_message}

Please analyze the user's response and determine their intent:

Return JSON with:
{{
  "Action": "proceed" or "retry" or "unclear",
  "Reasoning": "explanation of the user's intent",
  "Status": "success"
}}

Guidelines:
- "proceed": User wants to continue with the found sequence despite the name difference
- "retry": User wants to try again with a different gene name or search term
- "unclear": User's intent is not clear from their response
"""
    
    request_message = """**Gene Identity Confirmation Needed**

There's a mismatch between the gene you requested and what we found:

**You requested:** {target_gene}
**We found sequence for:** {found_gene}

The sequence appears to be for a different gene than what you requested.

**Would you like to:**
1. **Proceed** with the found sequence (if you think it's what you want)
2. **Try again** with a different gene name or identifier

Please let me know how you'd like to proceed."""

    @classmethod
    def step(cls, user_message, **kwargs):
        """Process user's decision about gene identity mismatch.
        
        If user confirms to proceed, continues to ConstructConfirmation.
        If user wants to retry, goes back to GeneInsertChoice.
        
        Args:
            user_message: User's confirmation/retry response
            **kwargs: Additional context from workflow
            
        Returns:
            Tuple of (Result_ProcessUserInput, next_state)
                - Routes to GeneInsertChoice if user wants to retry
                - Routes to ConstructConfirmation if user confirms to proceed
        """
        memory = kwargs.get("memory", {})
        gene_result = memory.get("GeneNameInput")
        gene_data = gene_result.result if gene_result else {}
        
        target_gene = gene_data.get("Target gene", "Unknown")
        found_gene = gene_data.get("FoundGeneName", "Unknown")
        
        # Format the request message with actual values
        formatted_request = cls.request_message.format(
            target_gene=target_gene,
            found_gene=found_gene
        )
        
        # Override request_message temporarily
        original_request_message = cls.request_message
        cls.request_message = formatted_request
        
        # Process user response
        prompt = cls.prompt_process.format(user_message=user_message)
        response = OpenAIChat.chat(prompt, use_GPT4=True)
        
        action = response.get("Action", "unclear").lower()
        
        if action == "retry":
            next_state = GeneInsertChoice
            response_text = "**Retrying Gene Selection**\n\nPlease provide a different gene name or identifier."
        elif action == "proceed":
            next_state = ConstructConfirmation
            response_text = f"**Proceeding with Found Gene**\n\nContinuing with sequence for **{found_gene}**."
        else:
            # Unclear response, ask for clarification but default to retry
            next_state = GeneInsertChoice
            response_text = "**Please Clarify**\n\nI'm not sure what you'd like to do. Let's try again with your gene selection."
        
        # Restore original request_message
        cls.request_message = original_request_message
        
        return (
            Result_ProcessUserInput(
                status="success",
                result=response,
                response=response_text,
            ),
            next_state,
        )


class ConstructConfirmation(BaseUserInputState):
    """State for displaying construct summary and requesting confirmation.
    
    Shows user a summary of the planned construct with:
    - Gene insert name
    - Plasmid backbone name
    
    Allows user to either proceed to output format selection or modify the gene.
    """
    prompt_process = PROMPT_PROCESS_SEQUENCE_VALIDATION
    request_message = PROMPT_REQUEST_SEQUENCE_VALIDATION

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
        custom_backbone_result = memory.get("CustomBackboneInput")
        
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
        custom_backbone_result = memory.get("CustomBackboneInput")

        # DO NOT PROVIDE DEFAULTS, Go back to the user if missing.
        
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
        breakpoint()
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


class StateStep2(BaseUserInputState):
    """Placeholder for backbone selection state"""
    pass
