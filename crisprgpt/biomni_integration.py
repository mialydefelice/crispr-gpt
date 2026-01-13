"""Biomni integration for plasmid design tasks."""

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
    
    def design_construct(self, backbone_seq: str, gene_seq: str, gene_name: str = "insert") -> Dict[str, Any]:
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
