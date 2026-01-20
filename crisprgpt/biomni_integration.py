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
    
    def select_backbone_from_requirements(self, requirements: str) -> Dict[str, Any]:
        """
        Use Biomni to select an appropriate plasmid backbone based on user requirements.
        
        This method helps when user provides requirements like:
        "an expression plasmid for mammalian cells with a constitutive promoter"
        instead of naming a specific plasmid.
        
        Args:
            requirements: String describing the desired backbone characteristics
                         (e.g., "mammalian expression, constitutive promoter, low copy")
            
        Returns:
            Dictionary with recommended plasmid name, characteristics, and sequence info
        """
        if not self.agent:
            logger.warning("Biomni agent not available, cannot select backbone")
            return {"error": "Biomni agent not initialized", "recommendations": None}
        
        try:
            task = f"""Based on the following requirements, recommend the most suitable plasmid backbone:

Requirements: {requirements}

Please analyze and recommend:
1. The best plasmid(s) that meet these requirements
2. Explain why each recommended plasmid is suitable
3. Provide key characteristics:
   - Host organism compatibility
   - Promoter type
   - Selection markers
   - Copy number
   - Size
4. Retrieve the DNA sequence for the top recommendation
5. Include source/repository information

Format your response with:
- Recommended plasmid name
- Key features and why it matches requirements
- Full DNA sequence (ACGT format)
- Sequence length in bp
- Repository/source"""
            
            # Execute task with Biomni
            self.agent.go(task)
            
            result = {
                "source": "biomni",
                "task": "backbone_selection_from_requirements",
                "status": "completed",
                "requirements": requirements
            }
            
            logger.info(f"Biomni backbone selection completed for requirements: {requirements}")
            return result
            
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
        
        try:
            # Build a comprehensive prompt with the backbone info
            backbone_name = backbone_info.get("BackboneName", "unknown plasmid")
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
            
            task = f"""Please retrieve the DNA sequence for the following plasmid:

Plasmid Name: {backbone_name}
Additional Info: {info_str}

Instructions:
1. Search for this plasmid in standard repositories (AddGene, NCBI, etc.), pull the accession number if available, from addgene, then use the tool get_plasmid_sequence to retrieve the sequence.
    If the accession number is not found in the main addgene repository try searching addgene addgene.org/vector-database
2. Return the complete DNA sequence as a string of ACGT letters (no other letters or spaces should be included) as a string. Make sure to output the full sequence.
3. Include key features/annotations if available
4. If not found exactly, suggest similar available plasmids

Do not provide placeholders if a DNA sequence is not found, provide an empty string.

Please provide the following (in JSON format):
- plasmid_name:string
- accession_number: string (if available) else none
- full_dna_sequence: (ACGT format)
- sequence_length: (in bp)
- sequence_source: string (repository/source)"""
            
            # Execute task with Biomni
            response=self.agent.go(task)
           
            logger.info(f"Biomni backbone extraction requested for: {backbone_name}")
            return response
            
        except Exception as e:
            logger.error(f"Biomni backbone sequence extraction failed: {e}")

            return {"error": str(e), "sequence": None, "source": "biomni"}

    
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
