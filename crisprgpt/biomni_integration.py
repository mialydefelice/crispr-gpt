"""Biomni integration for plasmid design tasks."""

import json
import re
from util import get_logger
from typing import Optional, Dict, Any

logger = get_logger(__name__)

try:
    from biomni.agent import A1
    BIOMNI_AVAILABLE = True
except ImportError:
    BIOMNI_AVAILABLE = False
    logger.warning("Biomni not available. Install with: pip install biomni")


class BiomniPlasmidAgent:
    """Wrapper for using Biomni to handle plasmid design tasks."""
    
    def __init__(self, llm: str = "gpt-4o", data_path: str = "./biomni_data"):
        """
        Initialize Biomni agent for plasmid tasks.
        
        Args:
            llm: LLM model to use (default: gpt-4o)
            data_path: Path to store Biomni data
        """
        self.llm = llm
        self.data_path = data_path
        self.agent = None
        
        if BIOMNI_AVAILABLE:
            try:
                # Initialize with skip datalake if not needed for your tasks
                self.agent = A1(
                    path=data_path,
                    llm=llm,
                    expected_data_lake_files=[]  # Skip datalake for faster initialization
                )
                logger.info(f"Biomni agent initialized with LLM: {llm}")
            except Exception as e:
                logger.error(f"Failed to initialize Biomni agent: {e}")
                self.agent = None
        else:
            logger.warning("Biomni not available - falling back to basic MCS handler")
    
    def find_mcs_in_plasmid(self, plasmid_sequence: str, plasmid_name: str = "unknown") -> Dict[str, Any]:
        """
        Use Biomni to identify MCS location in a plasmid.
        
        Args:
            plasmid_sequence: The plasmid sequence
            plasmid_name: Name/description of the plasmid
            
        Returns:
            Dictionary with MCS information
        """
        if not self.agent:
            logger.warning("Biomni agent not available, cannot identify MCS")
            return {"error": "Biomni agent not initialized"}
        
        try:
            task = f"""Analyze this plasmid sequence and identify the Multiple Cloning Site (MCS) location:
            
Plasmid: {plasmid_name}
Sequence length: {len(plasmid_sequence)} bp
First 500bp: {plasmid_sequence[:500]}

Please identify:
1. The location of the MCS (start and end positions)
2. Common restriction sites within the MCS
3. The most suitable position for inserting a gene insert
4. Any features to avoid (promoters, essential genes, etc.)

Return as JSON with keys: mcs_start, mcs_end, restriction_sites, insertion_point, rationale"""
            
            # Execute task with Biomni
            self.agent.go(task)
            
            # Extract results from agent's last execution
            # Note: You may need to adjust this based on Biomni's actual output format
            result = {
                "source": "biomni",
                "task_executed": task,
                "status": "success"
            }
            
            logger.info(f"Biomni analysis completed for plasmid: {plasmid_name}")
            return result
            
        except Exception as e:
            logger.error(f"Biomni task execution failed: {e}")
            return {"error": str(e), "source": "biomni"}
    
    def select_backbone_from_user_input(self, user_input: str, response) -> Dict[str, Any]:
        """
        Use Biomni to select an appropriate plasmid backbone based on user user_input.
        
        This method helps when user provides user_input like:
        "an expression plasmid for mammalian cells with a constitutive promoter"
        instead of naming a specific plasmid.
        
        Args:
            user_input: String describing the desired backbone characteristics
                         (e.g., "mammalian expression, constitutive promoter, low copy")
            response: Response from previous processing step

        Returns:
            Dictionary with recommended plasmid name, characteristics, and sequence info
        """
        if not self.agent:
            logger.warning("Biomni agent not available, cannot select backbone")
            return {"error": "Biomni agent not initialized", "recommendations": None}
        
        try:
            task = f"""
            You are an expert in molecular cloning and plasmid design.

Your task is to analyze the user's message and pre-processed response and recommend an appropriate plasmid backbone.
You are NOT retrieving DNA sequences and must NOT invent accession numbers or sequences.

────────────────────────
TASK
────────────────────────

Based on the user's input:
- Identify whether a specific plasmid backbone is explicitly mentioned.
- If a backbone is mentioned, normalize the name to a commonly used standard format.
- If no backbone is mentioned, recommend a well-known plasmid backbone that best fits the user's described use case.

Common use cases include (but are not limited to):
- Mammalian expression
- Bacterial cloning
- Lentiviral delivery
- AAV vectors
- CRISPR/Cas systems
- Reporter constructs

If multiple backbones are plausible, choose the most standard and widely adopted option.

────────────────────────
RULES
────────────────────────

- Do NOT retrieve or fabricate DNA sequences.
- Do NOT fabricate accession numbers, prefer addgene vector database catalog numbers.
- Use empty strings if information is unknown.
- If you are recommending (not confirming) a backbone, clearly indicate this.
- Output must be valid JSON only — no extra text.

────────────────────────
USER INPUT
────────────────────────
{user_input}

────────────────────────
USER INPUT
────────────────────────
{response}

────────────────────────
OUTPUT FORMAT (JSON ONLY)
────────────────────────
{{
  "BackboneName": "",
  "BackboneType": "",
  "IntendedUse": "",
  "Rationale": "",
  "Confidence": "high | medium | low",
  "Status": "confirmed | recommended"
}}
            
            """
            breakpoint()
            # Execute task with Biomni
            output = self.agent.go(task)
            
            logger.info(f"Biomni backbone selection completed for input: {user_input[:50]}...")
            return output
            
        except Exception as e:
            logger.error(f"Biomni backbone selection failed: {e}")
            return {"error": str(e), "source": "biomni"}
    
    def lookup_plasmid_by_name(self, backbone_info: dict) -> Dict[str, Any]:
        """
        Use Biomni to extract or look up a plasmid backbone sequence from limited info.
        
        This method helps retrieve the actual DNA sequence when user provides only
        a plasmid name or partial information.
        
        Args:
            backbone_info: Dictionary containing backbone information from user input
                          (e.g., name, promoter, selection marker, origin)
            
        Returns:
            Dictionary with extracted sequence and metadata
        """
        if not self.agent:
            logger.warning("Biomni agent not available, cannot extract backbone sequence")
            return {"error": "Biomni agent not initialized", "sequence": None}
        
        
        # Build a comprehensive prompt with the backbone info
        backbone_name = backbone_info.get("BackboneName", "")
        promoter = backbone_info.get("Promoter", "")
        marker = backbone_info.get("SelectionMarker", "")
        origin = backbone_info.get("Origin", "")
        
        info_parts = []
        if promoter:
            info_parts.append(f"Promoter: {promoter}")
        if marker:
            info_parts.append(f"Selection marker: {marker}")
        if origin:
            info_parts.append(f"Origin: {origin}")
        
        info_str = ", ".join(info_parts) if info_parts else "limited information"
        
        task = f"""You are an expert in plasmid sequence retrieval and curation.

Task:
Given a plasmid backbone name and optional additional information, retrieve the full DNA sequence for the plasmid from authoritative public repositories.

Inputs:
- backbone_name: {backbone_name}
- additional_info: {info_str}

Lookup Procedure (follow strictly in order):
1. Search Addgene by plasmid name.
- If found, record the Addgene accession / plasmid ID.
- Use the tool `get_plasmid_sequence` with the Addgene identifier to retrieve the full DNA sequence.
2. If not found in the primary Addgene search, search the Addgene Vector Database (addgene.org/vector-database).
3. If still not found, search other standard repositories (e.g., NCBI GenBank).
4. If an exact match is not found, identify the closest clearly related plasmid(s) and note them as suggestions.

Sequence Requirements:
- The DNA sequence must be complete and untruncated.
- The sequence must contain only uppercase A, C, G, and T characters.
- No whitespace, line breaks, numbers, or ambiguous bases are allowed.
- If a full verified sequence cannot be retrieved, return an empty string for the sequence fields.

Output Requirements:
- Return **only valid JSON**.
- Do not include explanations, comments, or markdown.
- Do not hallucinate accession numbers or sequences.
- If information is unavailable, use `null` (not placeholders or guesses).

JSON Schema (must match exactly):

{{
"plasmid_name": string,
"accession_number": string | null,
"full_dna_sequence": string,
"sequence_length": number,
"sequence_source": string,
"annotations": [
{{
    "feature_name": string,
    "start": number,
    "end": number,
    "description": string
}}
],
"suggested_similar_plasmids": [
{{
    "plasmid_name": string,
    "accession_number": string | null,
    "source": string
}}
]
}}

Field Rules:
- plasmid_name: Use the standardized name from the source database.
- accession_number: Repository identifier if available, otherwise "" Do not make up an accession number if one is not already provided.
- full_dna_sequence: Empty string if not found.
- sequence_length: Length of full_dna_sequence in base pairs (0 if sequence is empty).
- sequence_source: Name of the repository used (e.g., "Addgene", "NCBI GenBank"), or empty string if not found.
- annotations: Include key features (e.g., origin, antibiotic resistance, promoter) if available; otherwise return an empty array.
- suggested_similar_plasmids: Only include if no exact match is found; otherwise return an empty array."""
        
        # Execute task with Biomni
        response=self.agent.go(task)
        logger.info(f"Biomni backbone extraction requested for: {backbone_name}")

        # Add better response validation
        if response:
            if isinstance(response, list) and len(response) > 0 and 'solution' in response[-1]:
                logger.info(f"Biomni found backbone sequence solution for: {backbone_name}")
                return response
            elif isinstance(response, dict):
                logger.info(f"Biomni returned dict response for: {backbone_name}")
                return response
            elif isinstance(response, tuple):
                logger.info(f"Biomni returned tuple response for: {backbone_name}, converting to dict")
                # Try to convert tuple to a more usable format
                if len(response) >= 2:
                    return {
                        "plasmid_name": backbone_name,
                        "response_data": response[0] if response[0] else "",
                        "solution": response[1] if len(response) > 1 else "",
                        "source": "biomni",
                        "raw_response": response
                    }
                else:
                    return {
                        "plasmid_name": backbone_name,
                        "response_data": str(response),
                        "source": "biomni",
                        "raw_response": response
                    }
            else:
                logger.warning(f"Biomni returned unexpected format for {backbone_name}: {type(response)}")
                return {"error": "Unexpected response format", "sequence": None, "source": "biomni", "raw_response": str(response)}
        else:   
            logger.error(f"Biomni backbone sequence extraction failed: {backbone_info}")
            return {"error": str(backbone_info), "sequence": None, "source": "biomni"}

    
    def lookup_gene_sequence(self, gene_name: str) -> Dict[str, Any]:
        """
        Use Biomni to look up a gene sequence by name.
        
        This method searches for a gene by name and retrieves its coding sequence
        from authoritative databases like NCBI GenBank.
        
        Args:
            gene_name: Name or identifier of the gene (e.g., "GFP", "GAPDH", "TP53")
            
        Returns:
            Dictionary with sequence information or error details
        """

        if not self.agent:
            logger.warning("Biomni agent not available, cannot lookup gene sequence")
            return {"error": "Biomni agent not initialized", "sequence": None}
        
        # Add specific guidance for common genes to improve success rate
        common_genes = {
            "egfp": "Enhanced Green Fluorescent Protein from Aequorea victoria, ~717bp",
            "gfp": "Green Fluorescent Protein from Aequorea victoria, ~717bp", 
            "mcherry": "mCherry red fluorescent protein, ~711bp",
            "dsred": "DsRed red fluorescent protein from Discosoma, ~678bp",
            "gapdh": "Glyceraldehyde-3-phosphate dehydrogenase, housekeeping gene",
            "actb": "Beta-actin, cytoskeletal protein gene",
            "tp53": "Tumor protein p53, tumor suppressor gene",
            "myc": "MYC proto-oncogene transcription factor",
            "luciferase": "Firefly luciferase reporter gene, ~1650bp"
        }
        
        gene_hint = common_genes.get(gene_name.lower(), "")
        
        task = f"""Find the DNA coding sequence for gene: {gene_name}

I need the complete coding DNA sequence (CDS) for this gene. 
Please get the DNA sequence for {gene_name}. 
Start by trying to use an internet search to get the NCBI accession number. 
From there can look up the plasmid from NCBI, then use annotation tools to idenify the CDS and extrct the DNA sequence. 
If you can find an mRNA sequence, then translate this sequence to DNA using a tool. 
If you cannot find a tool to convert to DNA, then just return the mRNA sequence directly

Please:

1. Search for {gene_name} in molecular biology databases

2. Find the canonical/reference coding sequence 
3. Return the DNA sequence (not protein sequence)
4. Use only A, C, G, T characters (uppercase)
5. Provide the complete untruncated CDS
6. Do not make up a sequence if not found, return empty string if unavailable

For common genes like:
- EGFP/GFP: Enhanced Green Fluorescent Protein 
- mCherry: Red fluorescent protein
- GAPDH: Glyceraldehyde-3-phosphate dehydrogenase
- TP53: Tumor protein p53
- Actb/ACTB: Beta-actin

If the gene has multiple isoforms, use the most common/canonical version.
If species is not specified, assume the most commonly used version in research.

Return as JSON (Only!)with no additional text:
{{
  "gene_name": "standardized gene name",
  "sequence": "ATCG... (complete CDS sequence)",
  "sequence_length": number_of_base_pairs,
  "species": "species name",
  "accession": "database ID if available",
  "description": "brief description",
  "error": null_or_error_message
}}

Gene to look up: {gene_name}{f' - {gene_hint}' if gene_hint else ''}"""

        logger.info(f"Looking up gene sequence for: {gene_name}")
        response = self.agent.go(task)

        for attempt in range(2):
            # Retry if response is empty
            if response:
                break
            logger.warning(f"Biomni returned empty response for gene: {gene_name}, retrying ({attempt+1}/2)")
            response = self.agent.go(task)

        
        # Handle different response formats
        if response:
            # If response is a string, try to parse as JSON
            if isinstance(response[-1], str):
                match = re.search(r"<solution>\s*(\{.*?\})\s*</solution>", response[-1], re.DOTALL)
                if match:
                    json_str = match.group(1)
                    data = json.loads(json_str)
                    gene_sequence = data.get("sequence", "")
                    return data
                else:
                    logger.warning(f"Unexpected response format from Biomni for {gene_name}: {type(response)}")
                    return {"error": "Unexpected response format", "sequence": None, "raw_response": str(response)}
            else:
                # If response is not empty but not the expected format
                logger.warning(f"Unexpected response format from Biomni for {gene_name}: {type(response)}")
                return {"error": "Unexpected response format", "sequence": None, "raw_response": str(response)}
            """
            # If response is a dict, check for required fields
            if isinstance(response, dict):

                # Ensure we have a sequence field
                breakpoint()
                if "sequence" in response:
                    logger.info(f"Biomni gene lookup completed for: {gene_name}")
                    return response
                else:
                    # Try to extract sequence from other possible field names
                    for key in ["dna_sequence", "cds", "coding_sequence", "seq"]:
                        if key in response:
                            response["sequence"] = response[key]
                            logger.info(f"Found sequence in field '{key}' for: {gene_name}")
                            return response
                    
                    logger.warning(f"No sequence found in Biomni response for: {gene_name}")
                    return {"error": "No sequence in Biomni response", "sequence": None, "raw_response": response}
            if isinstance(response, tuple):
                logger.info(f"Biomni returned tuple response for gene: {gene_name}, converting to dict")
                # Try to convert tuple to a more usable format
                if len(response) >= 2 and isinstance(response[1], str):
                    match = re.search(r"<solution>\s*(\{.*?\})\s*</solution>", response[-1], re.DOTALL)
                    if match:
                        json_str = match.group(1)
                        data = json.loads(json_str)
                        gene_sequence = data.get("sequence", "")
                        description = data.get("description", "")

                    return {
                        "gene_name": gene_name,
                        "sequence": gene_sequence,
                        "description": description,
                        "source": "biomni",
                        "raw_response": response[-1]
                    }
                else:
                    breakpoint()
                    return {
                        "gene_name": gene_name,
                        "sequence": str(response),
                        "source": "biomni",
                        "raw_response": response
                    }
            """
        else:
            logger.warning(f"Empty response from Biomni for gene: {gene_name}")
            return {"error": "Empty response from Biomni", "sequence": None}


    
    def design_construct(self, backbone_seq: str, gene_seq: str, gene_name: str) -> Dict[str, Any]:
        """
        Use Biomni to design the best way to construct the plasmid.
        
        Args:
            backbone_seq: Backbone plasmid sequence
            gene_seq: Gene sequence to insert
            gene_name: Name of the gene
            
        Returns:
            Dictionary with construct design information
        """
        if not self.agent:
            logger.warning("Biomni agent not available, cannot design construct")
            return {"error": "Biomni agent not initialized"}
        
        try:
            task = f"""Design an expression construct by inserting a gene into a plasmid backbone:

Backbone: {len(backbone_seq)} bp plasmid
Gene to insert: {gene_name} ({len(gene_seq)} bp)

Please analyze and recommend:
1. Best insertion position (MCS, after promoter, etc.)
2. Any sequence modifications needed (stop codons, start codons)
3. Potential issues or incompatibilities
4. Final construct design strategy

Gene sequence start: {gene_seq[:100]}...
Backbone sequence start: {backbone_seq[:100]}..."""
            
            self.agent.go(task)
            
            result = {
                "source": "biomni",
                "gene_name": gene_name,
                "backbone_length": len(backbone_seq),
                "gene_length": len(gene_seq),
                "task_executed": True
            }
            
            logger.info(f"Biomni construct design completed for {gene_name}")
            return result
            
        except Exception as e:
            logger.error(f"Biomni construct design failed: {e}")
            return {"error": str(e), "source": "biomni"}
    
    def validate_construct(self, final_sequence: str, gene_name: str, backbone_name: str) -> Dict[str, Any]:
        """
        Use Biomni to validate the final construct.
        
        Args:
            final_sequence: Final construct sequence
            gene_name: Name of the inserted gene
            backbone_name: Name of the backbone plasmid
            
        Returns:
            Dictionary with validation results
        """
        if not self.agent:
            logger.warning("Biomni agent not available, cannot validate construct")
            return {"error": "Biomni agent not initialized"}
        
        try:
            task = f"""Validate this expression construct for potential issues:

Construct: {gene_name} in {backbone_name}
Total length: {len(final_sequence)} bp
Sequence start: {final_sequence[:200]}...

Please check for:
1. Frame shifts or stop codons in unwanted locations
2. Repeat sequences that might cause recombination
3. Methylation sites (GATC) that might affect expression
4. Overall sequence quality and synthesis feasibility
5. GC content analysis
6. Any red flags or warnings

Return assessment of construct quality."""
            
            self.agent.go(task)
            
            result = {
                "source": "biomni",
                "construct_name": f"{gene_name}_in_{backbone_name}",
                "sequence_length": len(final_sequence),
                "validated": True
            }
            
            logger.info(f"Biomni validation completed for {gene_name} construct")
            return result
            
        except Exception as e:
            logger.error(f"Biomni validation failed: {e}")
            return {"error": str(e), "source": "biomni"}


# Global instance
_biomni_agent = None


def get_biomni_agent(llm: str = "gpt-4o") -> Optional[BiomniPlasmidAgent]:
    """Get or create the global Biomni agent instance."""
    global _biomni_agent
    
    if _biomni_agent is None:
        _biomni_agent = BiomniPlasmidAgent(llm=llm)
    
    return _biomni_agent if _biomni_agent.agent else None
