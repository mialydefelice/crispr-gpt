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
from util import get_logger

logger = get_logger(__name__)


class StateEntry(BaseState):
    request_user_input = False

    @classmethod
    def step(cls, user_message, **kwargs):
        return Result_ProcessUserInput(response=PROMPT_REQUEST_ENTRY_EXPRESSION), StateStep1Backbone


class StateStep1Backbone(BaseUserInputState):
    prompt_process = PROMPT_PROCESS_STEP1_BACKBONE_INQUIRY_EXPRESSION
    request_message = PROMPT_REQUEST_STEP1_INQUIRY_EXPRESSION

    @classmethod
    def step(cls, user_message, **kwargs):
        prompt = cls.prompt_process.format(user_message=user_message)
        response = OpenAIChat.chat(prompt, use_GPT4=True)
        text_response = str(response)
        backbone_name = response.get("BackboneName", "").lower()
        
        # Check if user selected a custom backbone option
        if "custom" in backbone_name or response.get("Status", "").lower() == "needs_details":
            # Route to custom backbone state
            next_state = CustomBackboneInput
        else:
            # Standard backbone selected (pcDNA3.1(+) or pAG)
            next_state = GeneInsertSelection
        
        text_response += f" Final Result {backbone_name}"
        return (
            Result_ProcessUserInput(
                status="success",
                thoughts=response.get("Thoughts", ""),
                result=response,
                response=text_response,
            ),
            next_state,
        )


class CustomBackboneInput(BaseUserInputState):
    prompt_process = PROMPT_PROCESS_CUSTOM_BACKBONE_EXPRESSION
    request_message = PROMPT_REQUEST_CUSTOM_BACKBONE_EXPRESSION

    @classmethod
    def step(cls, user_message, **kwargs):
        prompt = cls.prompt_process.format(user_message=user_message)
        response = OpenAIChat.chat(prompt, use_GPT4=True)

        # Check if a sequence was actually provided
        sequence_provided = response.get("SequenceProvided", "no").lower() == "yes"
        sequence_length = response.get("SequenceLength")
        sequence_extracted = response.get("SequenceExtracted", "NA")
        
        if not sequence_provided or not sequence_length:
            # Graceful failure: user only provided name, not sequence
            error_message = """We weren't able to extract a plasmid sequence from your input. 

                To use a custom backbone, please provide:
                1. The plasmid name/identifier
                2. The actual DNA sequence (in FASTA or raw ACGT format)

                You can also try:
                - Providing the sequence from a GenBank file
                - Pasting the sequence from a plasmid repository
                - Going back to select a standard backbone (pcDNA3.1(+) or pAG)

                Please try again with the sequence included."""
            
            return (
                Result_ProcessUserInput(
                    status="error",
                    response=error_message,
                ),
                CustomBackboneInput,  # Allow user to try again
            )
        
        text_response = f"Custom Backbone: {response.get('BackboneName', 'Unknown')}\n"

        breakpoint()

        
        # Build summary of provided information
        details = []
        details.append(f"Sequence length: {sequence_length}")
        if response.get("Promoter"):
            details.append(f"Promoter: {response.get('Promoter')}")
        if response.get("SelectionMarker"):
            details.append(f"Selection marker: {response.get('SelectionMarker')}")
        if response.get("Origin"):
            details.append(f"Origin: {response.get('Origin')}")
        
        if details:
            text_response += " | ".join(details)
        
        # Store the backbone data in result so it gets saved to memory with state name "CustomBackboneInput"
        # This ensures the sequence and other details are available downstream
        return (
            Result_ProcessUserInput(
                status="success",
                result=response,  # This will be saved to memory["CustomBackboneInput"]
                response=text_response,
            ),
            GeneInsertSelection,
        )


class GeneInsertSelection(BaseUserInputState):
    prompt_process = PROMPT_PROCESS_AGENT1
    request_message = PROMPT_REQUEST_AGENT1

    @classmethod
    def step(cls, user_message, **kwargs):
        prompt = cls.prompt_process.format(user_message=user_message)
        response = OpenAIChat.chat(prompt, use_GPT4=True)
        response["original_request"] = user_message
        
        has_sequence = response.get("Has exact sequence", "no").lower() == "yes"
        
        if has_sequence:
            # User provided exact sequence, proceed directly
            text_response = f"Gene: {response.get('Target gene', 'Unknown')}\nSequence provided: {response.get('Sequence provided', 'N/A')}"
        else:
            # User provided gene name, agents will look it up
            text_response = f"Gene: {response.get('Target gene', 'Unknown')}\nWe will look up the sequence for you."
            if response.get("Suggested variants"):
                text_response += f"\nSuggested variants: {response.get('Suggested variants')}"
        
        return (
            Result_ProcessUserInput(
                status="success",
                result=response,
                response=text_response,
            ),
            ConstructConfirmation,
        )


class ConstructConfirmation(BaseUserInputState):
    prompt_process = PROMPT_PROCESS_SEQUENCE_VALIDATION
    request_message = PROMPT_REQUEST_SEQUENCE_VALIDATION

    @classmethod
    def step(cls, user_message, **kwargs):
        memory = kwargs.get("memory", {})
        
        # Extract data from previous states
        gene_result = memory.get("GeneInsertSelection")
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
            next_state = GeneInsertSelection
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
        gene_result = memory.get("GeneInsertSelection")
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
            next_state = GeneInsertSelection
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
    prompt_process = PROMPT_PROCESS_OUTPUT_FORMAT
    request_message = PROMPT_REQUEST_OUTPUT_FORMAT

    @classmethod
    def step(cls, user_message, **kwargs):
        prompt = cls.prompt_process.format(user_message=user_message)
        response = OpenAIChat.chat(prompt, use_GPT4=True)
        
        memory = kwargs.get("memory", {})
        
        # Retrieve stored design information from previous states
        gene_result = memory.get("GeneInsertSelection")
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
                    response="Error: No valid DNA sequence found in your input. Please provide a DNA sequence.",
                ),
                GeneInsertSelection,
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
                    response=f"Error: Could not find sequence for backbone '{backbone_name}' in plasmid library.",
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
    prompt_process = PROMPT_PROCESS_FINAL_SUMMARY
    request_message = PROMPT_REQUEST_FINAL_SUMMARY

    @classmethod
    def step(cls, user_message, **kwargs):
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
                GeneInsertSelection,
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
