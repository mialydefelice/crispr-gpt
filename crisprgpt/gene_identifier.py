"""Module for identifying genes from DNA sequences."""

from llm import OpenAIChat


class GeneIdentifier:
    """Identifies genes from DNA sequences when gene name is not provided."""
    
    PROMPT_IDENTIFY_GENE = """You are an expert in molecular biology and genomics. Given a DNA sequence, identify what gene it likely codes for.

DNA Sequence:
{sequence}

Please identify:
1. Most likely gene name/symbol
2. Organism/species if identifiable
3. Confidence level (high/medium/low)
4. Reasoning for your identification

Respond in JSON format:
{{
"Gene Name": "<gene_symbol>",
"Organism": "<organism>",
"Confidence": "<high|medium|low>",
"Reasoning": "<explanation>",
"Alternative Genes": "<other_possible_genes>"
}}
"""

    @staticmethod
    def identify_gene(sequence: str) -> dict:
        """
        Identify a gene from its DNA sequence.
        
        Args:
            sequence: DNA sequence string
            
        Returns:
            Dictionary with gene identification results
        """
        if not sequence or len(sequence) < 50:
            return {
                "Gene Name": "Unknown",
                "Organism": "Unknown",
                "Confidence": "low",
                "Reasoning": "Sequence too short for reliable identification"
            }
        
        # Truncate very long sequences to avoid excessive API calls
        truncated_seq = sequence[:2000] if len(sequence) > 2000 else sequence
        
        prompt = GeneIdentifier.PROMPT_IDENTIFY_GENE.format(sequence=truncated_seq)
        
        try:
            response = OpenAIChat.chat(prompt, use_GPT4=True)
            return response
        except Exception as e:
            return {
                "Gene Name": "Unknown",
                "Organism": "Unknown",
                "Confidence": "low",
                "Reasoning": f"Error identifying gene: {str(e)}"
            }
