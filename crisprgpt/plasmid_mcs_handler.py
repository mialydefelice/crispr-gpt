"""Module for handling plasmid MCS (Multiple Cloning Site) insertion."""

import re
from util import get_logger

logger = get_logger(__name__)


class MCSHandler:
    """Handles finding and inserting genes into plasmid MCS (Multiple Cloning Site)."""
    
    # Common MCS recognition patterns (restriction sites commonly found in MCS)
    COMMON_MCS_PATTERNS = {
        "EcoRI": "GAATTC",
        "BamHI": "GGATCC",
        "KpnI": "GGTACC",
        "XbaI": "TCTAGA",
        "SalI": "GTCGAC",
        "PstI": "CTGCAG",
        "NotI": "GCGGCCGC",
        "XhoI": "CTCGAG",
        "SmaI": "CCCGGG",
        "ApaI": "GGGCCC",
    }
    
    @staticmethod
    def find_mcs_sites(backbone_seq: str) -> list:
        """
        Find common restriction sites in the backbone that likely define the MCS.
        
        Args:
            backbone_seq: Backbone sequence string
            
        Returns:
            List of tuples: (site_name, position, pattern)
        """
        sites = []
        backbone_upper = backbone_seq.upper()
        
        for site_name, pattern in MCSHandler.COMMON_MCS_PATTERNS.items():
            matches = re.finditer(pattern, backbone_upper)
            for match in matches:
                sites.append({
                    "name": site_name,
                    "position": match.start(),
                    "end_position": match.end(),
                    "pattern": pattern
                })
        
        # Sort by position
        sites.sort(key=lambda x: x["position"])
        return sites
    
    @staticmethod
    def find_mcs_boundaries(backbone_seq: str) -> tuple:
        """
        Find the MCS boundaries by identifying flanking restriction sites.
        Typically, an MCS is bounded by two restriction sites.
        
        Args:
            backbone_seq: Backbone sequence string
            
        Returns:
            Tuple of (start_position, end_position) or None if not found
        """
        sites = MCSHandler.find_mcs_sites(backbone_seq)
        
        if len(sites) < 2:
            logger.warning("Could not find flanking restriction sites for MCS")
            return None
        
        # Assume MCS is between first and second major sites
        # In practice, you might need domain knowledge about specific plasmids
        start = sites[0]["end_position"]
        end = sites[1]["position"]
        
        # Make sure we have a valid range
        if end > start:
            return (start, end)
        
        return None
    
    @staticmethod
    def insert_gene_at_mcs(backbone_seq: str, gene_seq: str, insertion_point: int = None) -> dict:
        """
        Insert gene sequence into plasmid at MCS or specified position.
        
        Args:
            backbone_seq: Backbone sequence string
            gene_seq: Gene sequence to insert
            insertion_point: Optional specific position to insert. If None, use MCS detection.
            
        Returns:
            Dictionary with:
            - final_sequence: The resulting construct
            - insertion_position: Where the gene was inserted
            - method: How the insertion was performed ("mcs", "after_promoter", "concatenation")
        """
        if not backbone_seq or not gene_seq:
            return {
                "final_sequence": None,
                "insertion_position": None,
                "method": "error",
                "error": "Missing backbone or gene sequence"
            }
        
        backbone_upper = backbone_seq.upper()
        gene_upper = gene_seq.upper()
        
        # Try to find MCS boundaries
        if insertion_point is None:
            mcs_bounds = MCSHandler.find_mcs_boundaries(backbone_seq)
            if mcs_bounds:
                insertion_point = mcs_bounds[1]  # Insert at end of MCS
                method = "mcs"
            else:
                # Fallback: try to find promoter and insert after it
                promoter_match = re.search(r"CMV|SV40|EF1A|UBC", backbone_upper)
                if promoter_match:
                    insertion_point = promoter_match.end() + 100  # Insert 100bp after promoter start
                    method = "after_promoter"
                    logger.info(f"MCS not found, inserting after promoter at position {insertion_point}")
                else:
                    # Default: concatenate
                    insertion_point = len(backbone_seq)
                    method = "concatenation"
                    logger.warning("Could not find MCS or promoter, using concatenation")
        else:
            method = "custom_position"
        
        # Insert the gene
        if insertion_point < 0 or insertion_point > len(backbone_seq):
            insertion_point = len(backbone_seq)
        
        final_sequence = backbone_seq[:insertion_point] + gene_seq + backbone_seq[insertion_point:]
        
        return {
            "final_sequence": final_sequence,
            "insertion_position": insertion_point,
            "method": method,
            "mcs_sites": MCSHandler.find_mcs_sites(backbone_seq)
        }
