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
                - Routes to GeneInsertSelection if standard backbone selected
        """
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
                - Routes to GeneInsertSelection if sequence successfully extracted/selected
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
                    breakpoint()
                    biomni_result = biomni_agent.select_backbone_from_user_input(user_input=user_message, response=response)
                    breakpoint()
                    if not biomni_result.get("error"):
                        logger.info(f"Biomni successfully selected backbone to match requirements: {biomni_result.get('BackboneName')}")
                        # After Biomni selects backbone, ask user to confirm and provide sequence
                        confirmation_message = f"""Great! Based on your requirements, I've identified an appropriate plasmid backbone.""" 
                        
                    else:
                        logger.warning(f"Biomni could not select backbone: {biomni_result.get('error')}")
                except Exception as e:
                    logger.warning(f"Biomni backbone selection failed: {e}. Falling back to manual entry.")
                    

            if backbone_name != "":
                logger.info(f"User provided a backbone name, or one was selected for them given their requirements: {backbone_name}. Attempting to look up sequence...")
                
                logger.info(f"Using Biomni to look up backbone: {backbone_name}.")
                #Try to look up the plasmid by name using Biomni
                found_backbone_sequence = False
                max_attempts = 0
                for _ in range(3):
                    if found_backbone_sequence is False and max_attempts < 3:
                        try:
                            breakpoint()
                            # Use Biomni to look up plasmid by name
                            biomni_result = biomni_agent.lookup_plasmid_by_name(backbone_info=response)
                            breakpoint()
                            match = re.search(r"<solution>\s*(\{.*?\})\s*</solution>", biomni_result[-1], re.DOTALL)

                            if not match:
                                raise ValueError("No <solution> JSON block found")

                            json_str = match.group(1)

                            # 2. Load JSON into dictionary
                            data = json.loads(json_str)

                            # 3. Pull out the DNA sequence
                            plasmid_name = data.get("plasmid_name")
                            accession_number = data.get("accession_number")
                            full_dna_sequence = data.get("full_dna_sequence")
                            sequence_length = data.get("sequence_length")
                            source_repository = data.get("source_repository")
                            biomni_output_response = {
                                "PlasmidName": plasmid_name,
                                "AccessionNumber": accession_number,
                                "DNASequence": full_dna_sequence,
                                "SequenceLength": sequence_length,
                                "SourceRepository": source_repository}
                            max_attempts += 1
                            if len(full_dna_sequence) > 0:
                                found_backbone_sequence = True
                                response["SequenceExtracted"] = full_dna_sequence
                            breakpoint()

                            if not biomni_result.get("error"):
                                logger.info(f"Biomni successfully looked up backbone: {biomni_result.get('BackboneName')}")
                                # After Biomni looks up backbone, ask user to confirm and provide sequence
                                confirmation_message = f"""Great! I've found the plasmid backbone '{biomni_result.get('BackboneName')}'."""
                            else:
                                logger.warning(f"Biomni could not look up backbone: {biomni_result.get('error')}")
                        except Exception as e:
        
                            logger.warning(f"Biomni backbone selection failed: {e}. Falling back to manual entry.")
            else:
                # Have not verified this case yet.
                logger.warning(f"A backbone was not retrieved given the user input. Please try again.")
                breakpoint()
            # If user did not provide a plasmid name, but provided requirements instead, try to use Biomni to select appropriate backbone.

            breakpoint()
            #biomni_result
            #if backbone_ex
            # If we reach here, either no Biomni or requirements-based selection didn't work
            # Graceful failure: user only provided name or requirements, not sequence
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
        # Sequence was provided, proceed to next state
        else:
            logger.info(f"Edge case: User provided sequence for custom backbone: {backbone_name}, should not be encountering this condition in this state.")



        # Add the following to the final output

        sequence_length = length(sequence_extracted) if sequence_extracted else 0



        
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
                - Routes to GeneInsertSelection if user wants to modify
                - Routes to OutputFormatSelection if user confirms construct
        """
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
                - Returns errors to GeneInsertSelection if issues occur
        """
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
                - Routes to GeneInsertSelection if user wants to modify design
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
