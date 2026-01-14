import pandas as pd
from pathlib import Path
from util import get_logger

logger = get_logger(__name__)


class PlasmidLibraryReader:
    """Reader for plasmid library CSV file"""
    
    def __init__(self):
        self.df = None
        self.file_path = None
    
    @staticmethod
    def get_library_path():
        """Get the path to the plasmid library CSV file"""
        return Path(__file__).parent.parent.parent / "resources" / "plasmid_library.csv"
    
    def load_library(self):
        """Load the plasmid library from CSV file"""
        try:
            file_path = self.get_library_path()
            if not file_path.exists():
                logger.warning(f"Plasmid library file not found at {file_path}")
                return None
            
            self.df = pd.read_csv(file_path)
            self.file_path = file_path
            
            # Remove empty rows (rows where all values are NaN)
            self.df = self.df.dropna(how='all')
            
            logger.info(f"Loaded plasmid library with {len(self.df)} plasmids")
            return self.df
        except Exception as e:
            logger.error(f"Error loading plasmid library: {e}")
            return None
    
    def parse_gene_insert_library(self, species=None):
        """
        Parse and return the gene insert library.
        Since we're using plasmids, this returns the plasmid dataframe.
        Species parameter is kept for compatibility but not used in current implementation.
        """
        if self.df is None:
            self.load_library()
        
        if self.df is None:
            logger.warning("Could not load plasmid library")
            return pd.DataFrame()
        
        return self.df.copy()
    
    def filter_by_expression_level(self, expression_level):
        """Filter plasmids by expression level (low, medium, high)"""
        if self.df is None:
            self.load_library()
        
        if self.df is None:
            return pd.DataFrame()
        
        # Normalize expression level to match CSV format
        expression_level = expression_level.lower()
        
        # Filter dataframe
        filtered_df = self.df[
            self.df['Expression Level'].str.lower().str.contains(
                expression_level, na=False
            )
        ]
        
        logger.info(f"Filtered plasmids by expression level '{expression_level}': found {len(filtered_df)}")
        return filtered_df
    
    def get_plasmid_sequence_details(self, plasmid_name):
        """Filter plasmids by name or alternative names"""
        if self.df is None:
            self.load_library()
        
        if self.df is None:
            return pd.DataFrame()
        
        plasmid_name_lower = plasmid_name.lower()
        
        plasmid_details = (
            self.df.loc[
                self.df["Plasmid"].str.lower() == plasmid_name_lower
            ]
            .iloc[0]
        )

        return plasmid_details


def extract_info(user_request, prompt_process, df):
    """
    Extract information from user request and return relevant plasmid data.
    
    Args:
        user_request: User's request for plasmid information
        prompt_process: LLM prompt for processing the request
        df: Plasmid library dataframe
    
    Returns:
        Tuple of (filtered_dataframe, download_link_or_summary)
    """
    try:
        if df.empty:
            logger.warning("Plasmid library dataframe is empty")
            return pd.DataFrame(), "No plasmid library data available"
        
        # For now, return the full dataframe
        # In a real implementation, this would process the user request
        # through the LLM and filter accordingly
        
        download_link = "Plasmid library loaded successfully"
        
        return df, download_link
    
    except Exception as e:
        logger.error(f"Error extracting plasmid information: {e}")
        return pd.DataFrame(), f"Error: {str(e)}"


# Create a global instance for easy import
plasmid_library_reader = PlasmidLibraryReader()
